# Cedar — Casper Testnet Deployment (on-chain record)

> **This doc = the on-chain contract addresses + verifiable transactions.**
> For how to host the app (Railway/Docker), see the **Deployment** section of the
> [README](README.md#deployment).

The `VaultRouter` Odra contract is deployed and verified on **Casper Testnet**
(`casper-test`, protocol 2.0.0).

## Addresses (v3 — real CSPR custody, owner-gated)

**v3 custodies real CSPR** (not just records): `deposit` is payable and the
contract actually holds the attached motes; `withdraw` sends real CSPR back out;
an on-chain invariant guarantees the per-pool earmarks are backed **1:1** by the
contract's true CSPR balance.

| Item | Value |
|---|---|
| **Contract package hash (v3)** | `hash-afdbf6c32a6f6a54ec5aff5ebd8dbd2a92f672cd60e089cf7cb50ed55bc71d7c` |
| Owner / agent account | `01559240ecf20a26702948f0a076e85a1c430e1eb20b6627045c5cf43411ddfea2` |
| Package key name | `vault_router_v3` |

**Explorer:** https://testnet.cspr.live/contract-package/afdbf6c32a6f6a54ec5aff5ebd8dbd2a92f672cd60e089cf7cb50ed55bc71d7c

The contract is **owner-gated**: the installing account (the agent's key) is the
sole authorized caller of `deposit`/`reallocate`/`withdraw` (`Error::NotOwner = 4`),
enforcing on-chain that server-side signing is Cedar's only actuation path.

## Verifiable transactions (v3 — real custody lifecycle)

Each executed without revert on `casper-test`; together they prove the contract
holds and moves **real CSPR** (deposited 20, withdrew 5 → 15 CSPR custodied),
with `get_backing() == get_total_value()` verified true on-chain.

| Action | Effect | Transaction |
|---|---|---|
| install (`init` owner ctor) | v3 deployed, caller = owner | [`d1bd4d3b…1896`](https://testnet.cspr.live/deploy/d1bd4d3b6ba20a3b01fe7317663ab91c318b340a2eb452262d5c192cf05a1896) |
| **`deposit(PoolA)`** payable, +20 CSPR | backing **0 → 20 CSPR** (real custody) | [`d9be9302…dcf6`](https://testnet.cspr.live/transaction/d9be93020cdd8c3d599c74626430bb6c0e3c3284e61d37223efa825149d0dcf6) |
| **`reallocate(PoolA→PoolB, 8)`** — the agent's action | earmarks 12 / 8, backing unchanged | [`a4536350…67c0`](https://testnet.cspr.live/transaction/a453635090e1ab68ec360b98380a7ebc716f1aa40439f537bfdf5d7f4f0b67c0) |
| **`withdraw(PoolB, 5)`** | real motes leave → backing **20 → 15 CSPR** | [`be652b91…cd28`](https://testnet.cspr.live/transaction/be652b91158607afc5501b689afae44e16b437db47ddea3f5537f273c8d2cd28) |

### Prior version (v2 — records-only, deploy history)

`hash-2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d` — the
first owner-gated router (tracked allocations as numbers). Superseded by v3's
real custody; remains on testnet as history.

## On-chain state read-back

The agent reads allocations **from chain** each cycle (`agent/chain_state.py`),
not from its local cache: contract named key `state` is Odra's storage dictionary;
item key = `hex(blake2b256(field_index_be_u32 ++ pool_u8))` with `allocations` at
field index 2; values are `List<U8>`-wrapped `ToBytes(U512)`. Verified live against
the deployed contract (PoolA=600, PoolB=400 after the seed txns). RPC failure falls
back to the local cache with a logged warning — never silently.

The `reallocate` call is the transaction-producing on-chain action Cedar's agent
actuates each cycle. It succeeded without revert after `deposit`, which proves the
recorded allocation was read and mutated correctly on-chain — the contract reverts
with `InsufficientAllocation` if `get_allocation(from_pool) < amount`.

## Reproducing the deploy

```bash
# 1. build the size-optimized wasm
cd contracts/vault_router
RUSTFLAGS='--cfg odra_module="VaultRouter"' \
  cargo build --release --lib --target wasm32-unknown-unknown

# 2. install (needs a funded testnet key at "Account 1_secret_key.pem")
casper-client put-deploy \
  --node-address https://node.testnet.casper.network/rpc \
  --chain-name casper-test \
  --secret-key "Account 1_secret_key.pem" \
  --payment-amount 800000000000 \
  --session-path target/wasm32-unknown-unknown/release/vault_router.wasm \
  --session-arg "odra_cfg_package_hash_key_name:string='vault_router'" \
  --session-arg "odra_cfg_allow_key_override:bool='false'" \
  --session-arg "odra_cfg_is_upgradable:bool='false'" \
  --session-arg "odra_cfg_is_upgrade:bool='false'"
```

### Calling entrypoints

`PoolId` is a fieldless Odra enum → encoded as `u8` (PoolA=0, PoolB=1, PoolC=2).
Args are named by parameter.

```bash
# deposit
casper-client put-deploy … \
  --session-package-hash hash-27131991299036f9116c2754a042d682e50dfd4fe66e84c64111b3dae850e493 \
  --session-entry-point deposit \
  --session-arg "pool_id:u8='0'" --session-arg "amount:u512='1000'"

# reallocate
casper-client put-deploy … \
  --session-package-hash hash-2713…e493 \
  --session-entry-point reallocate \
  --session-arg "from_pool:u8='0'" --session-arg "to_pool:u8='1'" --session-arg "amount:u512='400'"
```

## Notes / gotchas learned

- Odra 2.8 requires a **nightly** toolchain (`box_patterns`) — pinned in
  `contracts/vault_router/rust-toolchain.toml`.
- Install requires four runtime args: `odra_cfg_package_hash_key_name`,
  `odra_cfg_allow_key_override`, `odra_cfg_is_upgradable`, `odra_cfg_is_upgrade`.
  Missing any → Odra error `64658` (`MissingArg`, = 64536 + 122).
- On Casper 2.0 fixed-price mode a failed deploy still charges the full
  `--payment-amount`. The 292 KB wasm install consumes ~289 CSPR; use an
  800 CSPR limit for headroom.
