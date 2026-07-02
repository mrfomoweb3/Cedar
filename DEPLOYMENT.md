# Cedar — Casper Testnet Deployment

The `VaultRouter` Odra contract is deployed and verified on **Casper Testnet**
(`casper-test`, protocol 2.0.0).

## Addresses

| Item | Value |
|---|---|
| Contract package hash | `hash-27131991299036f9116c2754a042d682e50dfd4fe66e84c64111b3dae850e493` |
| Contract hash (v1) | `contract-a941bdd092c3b64a5697ed9b73713175962202c9fcaab7c616f4987b2e45e362` |
| Deployer account | `0202a8ff98bbb32ec9b6f917a0d9646ba6f3a30f88aefa7290b6e3ec6be88bf4225a` |
| Package key name | `vault_router` |

**Explorer:** https://testnet.cspr.live/contract-package/27131991299036f9116c2754a042d682e50dfd4fe66e84c64111b3dae850e493

## Verifiable transactions

| Action | Deploy hash / explorer |
|---|---|
| Contract install | [`c25e6514…719cf`](https://testnet.cspr.live/deploy/c25e651472cb0e41f4dc87a8a9744a0e0525cbeef90f51cb8e54a2f2049719cf) |
| `deposit(PoolA, 1000)` | [`630159ae…3efd9`](https://testnet.cspr.live/deploy/630159ae40397de07b7f2fa565ade24ab9ca6ca50c45272e0bddba5e18d3efd9) |
| `reallocate(PoolA→PoolB, 400)` | [`c4318a8b…a996`](https://testnet.cspr.live/deploy/c4318a8b38caf8f84be7bb16fb083bc4bf2d02961e728ed0284553531b8ea996) |

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
