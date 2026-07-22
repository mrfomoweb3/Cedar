//! Livenet script: proves VaultRouter v3 custodies REAL CSPR on Casper testnet.
//! Does a payable deposit, an autonomous-style reallocate, and a real withdraw,
//! printing the contract's on-chain CSPR backing before/after.
//!
//! Run with:
//!   ODRA_CASPER_LIVENET_NODE_ADDRESS=https://node.testnet.casper.network/rpc \
//!   ODRA_CASPER_LIVENET_CHAIN_NAME=casper-test \
//!   ODRA_CASPER_LIVENET_SECRET_KEY_PATH=keys/rotated_2026/secret_key.pem \
//!   cargo run --bin cedar_livenet --features livenet

use std::str::FromStr;

use odra::casper_types::U512;
use odra::host::{HostRef, HostRefLoader};
use odra::prelude::*;
use vault_router::{PoolId, VaultRouter};

const PACKAGE: &str =
    "hash-afdbf6c32a6f6a54ec5aff5ebd8dbd2a92f672cd60e089cf7cb50ed55bc71d7c";

const CSPR: u64 = 1_000_000_000;

fn main() {
    let env = odra_casper_livenet_env::env();
    let address = Address::from_str(PACKAGE).expect("valid package hash");
    let mut vault = VaultRouter::load(&env, address);

    // (the contract's main purse only exists once the first payable deposit
    // funds it, so we read backing *after* depositing)

    // 1. deposit 20 real CSPR into PoolA (payable — motes now custodied).
    // Payable calls run through Odra's proxy (creates a cargo purse + transfer),
    // so they need a larger gas budget than a plain entrypoint.
    env.set_gas(25 * CSPR);
    vault
        .with_tokens(U512::from(20 * CSPR))
        .deposit(PoolId::PoolA);
    println!("backing after deposit: {}", vault.get_backing());

    // 2. reallocate 8 CSPR PoolA -> PoolB (the autonomous action)
    env.set_gas(6 * CSPR);
    vault.reallocate(PoolId::PoolA, PoolId::PoolB, U512::from(8 * CSPR));
    println!("PoolA earmark:         {}", vault.get_allocation(PoolId::PoolA));
    println!("PoolB earmark:         {}", vault.get_allocation(PoolId::PoolB));

    // 3. withdraw 5 real CSPR from PoolB back to the owner
    env.set_gas(15 * CSPR);
    vault.withdraw(PoolId::PoolB, U512::from(5 * CSPR), env.caller());
    println!("backing after withdraw:{}", vault.get_backing());
    println!("total earmarks:        {}", vault.get_total_value());
    println!(
        "invariant backing==earmarks: {}",
        vault.get_backing() == vault.get_total_value()
    );
}
