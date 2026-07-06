# Cedar — Casper Testnet Deployment (on-chain record)

> **This doc = the on-chain contract addresses + verifiable transactions.**
> For how to host the app (Railway/Docker), see the **Deployment** section of the
> [README](README.md#deployment).

The `VaultRouter` Odra contract is deployed and verified on **Casper Testnet**
(`casper-test`, protocol 2.0.0).

## Addresses (current — owner-gated)

The signing key was **rotated** for security hygiene; these are the current,
canonical addresses. Prior installs remain on testnet as deploy history.

| Item | Value |
|---|---|
| **Contract package hash** | `hash-2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d` |
| Owner / agent account | `01559240ecf20a26702948f0a076e85a1c430e1eb20b6627045c5cf43411ddfea2` |
| Package key name | `vault_router` |

**Explorer:** https://testnet.cspr.live/contract-package/2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d

The contract is **owner-gated**: the installing account (the agent's key) is the
sole authorized caller of `deposit`/`reallocate` (`Error::NotOwner = 4`), enforcing
on-chain that server-side signing is Cedar's only actuation path.

## Verifiable transactions (current contract)

| Action | Deploy hash / explorer |
|---|---|
| install (with `init` owner ctor) | [`a0715b52…97e6`](https://testnet.cspr.live/deploy/a0715b52f55d91e9008357515608d967bf7e3d48280093b684d4136e6c1e97e6) |
| `deposit(PoolA, 1000)` | [`69331b0f…f0de`](https://testnet.cspr.live/deploy/69331b0f8c9b52b6cec1e997012548634f0fb06d2ce1ced72b83717e769cf0de) |
| `reallocate(PoolA→PoolB, 400)` — tx-producing action | [`0b80e11e…4ac7`](https://testnet.cspr.live/deploy/0b80e11e8bb6127930e259fde4767f9a2f7a7954e143cb49ef792c96b9194ac7) |

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
