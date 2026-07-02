#![cfg_attr(not(test), no_std)]

//! Cedar VaultRouter -- a minimal Odra vault router for the Casper Agentic
//! Buildathon. Records allocations across a fixed, pre-vetted set of three
//! pools and lets the Cedar agent move recorded allocation between them.
//!
//! Deliberately minimal: judged on "working", not sophistication. The
//! `reallocate` entrypoint is the transaction-producing on-chain component.

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

/// Errors surfaced to callers.
#[odra::odra_error]
pub enum Error {
    /// reallocate requested more than the from-pool currently holds.
    InsufficientAllocation = 1,
    /// from_pool and to_pool are the same.
    SamePool = 2,
    /// amount was zero.
    ZeroAmount = 3,
}

#[odra::module]
pub struct VaultRouter {
    /// pool index (0..3) -> recorded allocation.
    allocations: Mapping<u8, U512>,
}

#[odra::module]
impl VaultRouter {
    /// Record an allocation into `pool`. Emits `Deposited`.
    pub fn deposit(&mut self, pool_id: PoolId, amount: U512) {
        if amount.is_zero() {
            self.env().revert(Error::ZeroAmount);
        }
        let key = pool_id.index();
        let current = self.allocations.get_or_default(&key);
        self.allocations.set(&key, current + amount);
        self.env().emit_event(Deposited { pool: pool_id, amount });
    }

    /// Move recorded allocation from one pool to another. Emits `Reallocated`.
    /// This is Cedar's transaction-producing on-chain action.
    pub fn reallocate(&mut self, from_pool: PoolId, to_pool: PoolId, amount: U512) {
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

    /// Current recorded allocation for a pool.
    pub fn get_allocation(&self, pool_id: PoolId) -> U512 {
        self.allocations.get_or_default(&pool_id.index())
    }

    /// Sum of allocations across all pools.
    pub fn get_total_value(&self) -> U512 {
        PoolId::all()
            .iter()
            .fold(U512::zero(), |acc, p| acc + self.allocations.get_or_default(&p.index()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, NoArgs};

    fn deploy() -> VaultRouterHostRef {
        let env = odra_test::env();
        VaultRouter::deploy(&env, NoArgs)
    }

    #[test]
    fn deposit_records_allocation() {
        let mut c = deploy();
        c.deposit(PoolId::PoolA, U512::from(100));
        assert_eq!(c.get_allocation(PoolId::PoolA), U512::from(100));
        assert_eq!(c.get_total_value(), U512::from(100));
    }

    #[test]
    fn reallocate_moves_between_pools() {
        let mut c = deploy();
        c.deposit(PoolId::PoolA, U512::from(100));
        c.reallocate(PoolId::PoolA, PoolId::PoolB, U512::from(40));
        assert_eq!(c.get_allocation(PoolId::PoolA), U512::from(60));
        assert_eq!(c.get_allocation(PoolId::PoolB), U512::from(40));
        assert_eq!(c.get_total_value(), U512::from(100));
    }

    #[test]
    fn reallocate_rejects_insufficient() {
        let mut c = deploy();
        c.deposit(PoolId::PoolA, U512::from(10));
        let err = c.try_reallocate(PoolId::PoolA, PoolId::PoolB, U512::from(50));
        assert!(err.is_err());
    }

    #[test]
    fn reallocate_rejects_same_pool() {
        let mut c = deploy();
        c.deposit(PoolId::PoolA, U512::from(10));
        assert!(c.try_reallocate(PoolId::PoolA, PoolId::PoolA, U512::from(5)).is_err());
    }
}
