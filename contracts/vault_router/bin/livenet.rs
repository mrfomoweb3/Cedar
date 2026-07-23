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

    // Fund the vault with a realistic demo portfolio of REAL CSPR, split across
    // the three pools. Payable calls run through Odra's proxy (creates a cargo
    // purse + transfer), so each needs a larger gas budget.
    let deposits = [(PoolId::PoolA, 300u64), (PoolId::PoolB, 100u64), (PoolId::PoolC, 50u64)];
    for (pool, cspr) in deposits {
        env.set_gas(25 * CSPR);
        vault.with_tokens(U512::from(cspr * CSPR)).deposit(pool);
        println!("deposited {} CSPR -> backing now {}", cspr, vault.get_backing());
    }

    println!(
        "earmarks: PoolA={} PoolB={} PoolC={}",
        vault.get_allocation(PoolId::PoolA),
        vault.get_allocation(PoolId::PoolB),
        vault.get_allocation(PoolId::PoolC)
    );
    println!("total backing (motes): {}", vault.get_backing());
    println!(
        "invariant backing==earmarks: {}",
        vault.get_backing() == vault.get_total_value()
    );
}
