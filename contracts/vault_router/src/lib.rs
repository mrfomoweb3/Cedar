#![cfg_attr(not(test), no_std)]

//! Cedar VaultRouter — a native-CSPR custody vault for the Casper Agentic
//! Buildathon.
//!
//! v3 custodies **real CSPR**: `deposit` is payable and the attached motes are
//! held by the contract; `reallocate` re-earmarks that custodied capital across
//! a fixed, pre-vetted set of three strategy pools; `withdraw` sends real CSPR
//! back out. An on-chain invariant guarantees the per-pool earmarks are always
//! backed 1:1 by the contract's actual CSPR balance — so the "allocation" is
//! never a number floating free of real value.
//!
//! Every mutating entrypoint is owner-gated: server-side signing by the Cedar
//! agent is the sole actuation path, and the contract enforces it. `reallocate`
//! is the transaction-producing on-chain action the agent runs autonomously.

extern crate alloc;

use odra::casper_types::U512;
use odra::prelude::*;

/// Fixed, pre-vetted pool set (mirrors `POOL_IDS` in the Python agent).
#[odra::odra_type]
#[derive(Copy)]
pub enum PoolId {
    PoolA,
    PoolB,
    PoolC,
}

impl PoolId {
    /// Stable storage key for the internal Mapping.
    fn index(&self) -> u8 {
        match self {
            PoolId::PoolA => 0,
            PoolId::PoolB => 1,
            PoolId::PoolC => 2,
        }
    }

    fn all() -> [PoolId; 3] {
        [PoolId::PoolA, PoolId::PoolB, PoolId::PoolC]
    }
}

#[odra::event]
pub struct Deposited {
    pub pool: PoolId,
    pub amount: U512,
}

#[odra::event]
pub struct Reallocated {
    pub from_pool: PoolId,
    pub to_pool: PoolId,
    pub amount: U512,
}

#[odra::event]
pub struct Withdrawn {
    pub pool: PoolId,
    pub amount: U512,
    pub to: Address,
}

/// Errors surfaced to callers.
#[odra::odra_error]
pub enum Error {
    /// reallocate/withdraw requested more than the from-pool currently holds.
    InsufficientAllocation = 1,
    /// from_pool and to_pool are the same.
    SamePool = 2,
    /// amount (or attached value) was zero.
    ZeroAmount = 3,
    /// caller is not the agent owner.
    NotOwner = 4,
}

#[odra::module]
pub struct VaultRouter {
    /// The agent account set at install time; sole authorized caller of the
    /// mutating entrypoints.
    owner: Var<Address>,
    /// pool index (0..3) -> earmarked CSPR (motes), backed 1:1 by self_balance.
    allocations: Mapping<u8, U512>,
}

#[odra::module]
impl VaultRouter {
    /// Constructor: the installing account becomes the owner.
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
    }

    /// The authorized agent account.
    pub fn get_owner(&self) -> Address {
        self.owner.get().unwrap_or_revert(&self.env())
    }

    fn assert_owner(&self) {
        if self.env().caller() != self.get_owner() {
            self.env().revert(Error::NotOwner);
        }
    }

    /// Deposit **real CSPR** into `pool`. Payable — the attached motes are now
    /// custodied by the contract. Owner-only. Emits `Deposited`.
    #[odra(payable)]
    pub fn deposit(&mut self, pool_id: PoolId) {
        self.assert_owner();
        let amount = self.env().attached_value();
        if amount.is_zero() {
            self.env().revert(Error::ZeroAmount);
        }
        let key = pool_id.index();
        let current = self.allocations.get_or_default(&key);
        self.allocations.set(&key, current + amount);
        self.env().emit_event(Deposited { pool: pool_id, amount });
    }

    /// Re-earmark custodied CSPR from one pool to another. Owner-only. No CSPR
    /// leaves the contract — the total backing is unchanged — but the agent has
    /// moved real, custodied capital between strategies. Emits `Reallocated`.
    /// This is Cedar's transaction-producing on-chain action.
    pub fn reallocate(&mut self, from_pool: PoolId, to_pool: PoolId, amount: U512) {
        self.assert_owner();
        if amount.is_zero() {
            self.env().revert(Error::ZeroAmount);
        }
        if from_pool == to_pool {
            self.env().revert(Error::SamePool);
        }
        let from_key = from_pool.index();
        let to_key = to_pool.index();
        let from_balance = self.allocations.get_or_default(&from_key);
        if from_balance < amount {
            self.env().revert(Error::InsufficientAllocation);
        }
        self.allocations.set(&from_key, from_balance - amount);
        let to_balance = self.allocations.get_or_default(&to_key);
        self.allocations.set(&to_key, to_balance + amount);
        self.env().emit_event(Reallocated { from_pool, to_pool, amount });
    }

    /// Withdraw **real CSPR** from `pool` to `to`. Owner-only. Sends motes out
    /// of the contract and decrements the earmark. Emits `Withdrawn`.
    pub fn withdraw(&mut self, pool_id: PoolId, amount: U512, to: Address) {
        self.assert_owner();
        if amount.is_zero() {
            self.env().revert(Error::ZeroAmount);
        }
        let key = pool_id.index();
        let balance = self.allocations.get_or_default(&key);
        if balance < amount {
            self.env().revert(Error::InsufficientAllocation);
        }
        self.allocations.set(&key, balance - amount);
        self.env().transfer_tokens(&to, &amount);
        self.env().emit_event(Withdrawn { pool: pool_id, amount, to });
    }

    /// Current earmarked CSPR for a pool (motes).
    pub fn get_allocation(&self, pool_id: PoolId) -> U512 {
        self.allocations.get_or_default(&pool_id.index())
    }

    /// Sum of earmarks across all pools (motes).
    pub fn get_total_value(&self) -> U512 {
        PoolId::all()
            .iter()
            .fold(U512::zero(), |acc, p| acc + self.allocations.get_or_default(&p.index()))
    }

    /// The contract's **actual** custodied CSPR balance (motes). The invariant
    /// `get_backing() == get_total_value()` holds after every entrypoint, so
    /// earmarks are provably backed by real value.
    pub fn get_backing(&self) -> U512 {
        self.env().self_balance()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, HostRef, NoArgs};

    fn deploy() -> VaultRouterHostRef {
        let env = odra_test::env();
        VaultRouter::deploy(&env, NoArgs)
    }

    const CSPR: u64 = 1_000_000_000; // 1 CSPR in motes

    #[test]
    fn deposit_custodies_real_cspr() {
        let mut c = deploy();
        c.with_tokens(U512::from(100 * CSPR)).deposit(PoolId::PoolA);
        assert_eq!(c.get_allocation(PoolId::PoolA), U512::from(100 * CSPR));
        assert_eq!(c.get_total_value(), U512::from(100 * CSPR));
        // the contract actually holds the CSPR
        assert_eq!(c.get_backing(), U512::from(100 * CSPR));
    }

    #[test]
    fn reallocate_moves_between_pools_backing_unchanged() {
        let mut c = deploy();
        c.with_tokens(U512::from(100 * CSPR)).deposit(PoolId::PoolA);
        c.reallocate(PoolId::PoolA, PoolId::PoolB, U512::from(40 * CSPR));
        assert_eq!(c.get_allocation(PoolId::PoolA), U512::from(60 * CSPR));
        assert_eq!(c.get_allocation(PoolId::PoolB), U512::from(40 * CSPR));
        // invariant: earmarks still fully backed by custodied CSPR
        assert_eq!(c.get_total_value(), c.get_backing());
    }

    #[test]
    fn withdraw_sends_real_cspr_out() {
        let env = odra_test::env();
        let mut c = VaultRouter::deploy(&env, NoArgs);
        c.with_tokens(U512::from(100 * CSPR)).deposit(PoolId::PoolA);
        let recipient = env.get_account(1);
        let before = env.balance_of(&recipient);
        c.withdraw(PoolId::PoolA, U512::from(30 * CSPR), recipient);
        assert_eq!(c.get_allocation(PoolId::PoolA), U512::from(70 * CSPR));
        // real motes left the contract and reached the recipient
        assert_eq!(c.get_backing(), U512::from(70 * CSPR));
        assert_eq!(env.balance_of(&recipient), before + U512::from(30 * CSPR));
        // invariant holds
        assert_eq!(c.get_total_value(), c.get_backing());
    }

    #[test]
    fn reallocate_rejects_insufficient() {
        let mut c = deploy();
        c.with_tokens(U512::from(10 * CSPR)).deposit(PoolId::PoolA);
        assert!(c
            .try_reallocate(PoolId::PoolA, PoolId::PoolB, U512::from(50 * CSPR))
            .is_err());
    }

    #[test]
    fn reallocate_rejects_same_pool() {
        let mut c = deploy();
        c.with_tokens(U512::from(10 * CSPR)).deposit(PoolId::PoolA);
        assert!(c
            .try_reallocate(PoolId::PoolA, PoolId::PoolA, U512::from(5 * CSPR))
            .is_err());
    }

    #[test]
    fn withdraw_rejects_insufficient() {
        let env = odra_test::env();
        let mut c = VaultRouter::deploy(&env, NoArgs);
        c.with_tokens(U512::from(10 * CSPR)).deposit(PoolId::PoolA);
        assert!(c
            .try_withdraw(PoolId::PoolA, U512::from(50 * CSPR), env.get_account(1))
            .is_err());
    }

    #[test]
    fn installer_is_owner() {
        let env = odra_test::env();
        let c = VaultRouter::deploy(&env, NoArgs);
        assert_eq!(c.get_owner(), env.get_account(0));
    }

    #[test]
    fn non_owner_cannot_mutate() {
        let env = odra_test::env();
        let mut c = VaultRouter::deploy(&env, NoArgs);
        c.with_tokens(U512::from(100 * CSPR)).deposit(PoolId::PoolA);
        env.set_caller(env.get_account(1));
        assert!(c
            .with_tokens(U512::from(CSPR))
            .try_deposit(PoolId::PoolA)
            .is_err());
        assert!(c
            .try_reallocate(PoolId::PoolA, PoolId::PoolB, U512::from(CSPR))
            .is_err());
        assert!(c
            .try_withdraw(PoolId::PoolA, U512::from(CSPR), env.get_account(1))
            .is_err());
        env.set_caller(env.get_account(0));
        assert_eq!(c.get_allocation(PoolId::PoolA), U512::from(100 * CSPR));
    }
}
