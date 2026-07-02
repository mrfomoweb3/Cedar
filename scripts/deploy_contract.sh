#!/usr/bin/env bash
# Deploy the Cedar VaultRouter to Casper Testnet.
#
# Prereqs:
#   - cargo-odra:  cargo install cargo-odra
#   - casper-client: https://docs.casper.network/developers/prerequisites/
#   - a funded testnet secret key at $CASPER_SECRET_KEY (default: ./secret_key.pem)
#   - testnet CSPR from the faucet: https://testnet.cspr.live/tools/faucet
#
# Usage:
#   scripts/deploy_contract.sh
set -euo pipefail

NODE_ADDRESS="${CASPER_NODE_URL:-https://node.testnet.casper.network/rpc}"
CHAIN_NAME="${CASPER_CHAIN:-casper-test}"
SECRET_KEY="${CASPER_SECRET_KEY:-./secret_key.pem}"
PAYMENT="${CASPER_DEPLOY_PAYMENT:-200000000000}"  # 200 CSPR

cd "$(dirname "$0")/../contracts/vault_router"

MODULE="VaultRouter"
if command -v cargo-odra >/dev/null 2>&1; then
  echo ">> Building contract wasm via cargo-odra..."
  cargo odra build
  WASM_PATH="wasm/${MODULE}.wasm"
else
  echo ">> cargo-odra not found; building wasm directly with odra_module cfg..."
  RUSTFLAGS="--cfg odra_module=\"${MODULE}\"" \
    cargo build --release --lib --target wasm32-unknown-unknown
  WASM_PATH="target/wasm32-unknown-unknown/release/vault_router.wasm"
fi

if [[ ! -f "$WASM_PATH" ]]; then
  echo "!! Expected wasm at $WASM_PATH not found. Check the build output above." >&2
  exit 1
fi
echo ">> wasm ready: $WASM_PATH ($(wc -c < "$WASM_PATH") bytes)"

echo ">> Deploying $WASM_PATH to $CHAIN_NAME ($NODE_ADDRESS)..."
casper-client put-deploy \
  --node-address "$NODE_ADDRESS" \
  --chain-name "$CHAIN_NAME" \
  --secret-key "$SECRET_KEY" \
  --payment-amount "$PAYMENT" \
  --session-path "$WASM_PATH" \
  --session-entry-point "call"

echo ">> Deploy submitted. Track it on https://testnet.cspr.live and record the"
echo "   resulting contract hash into VAULT_ROUTER_HASH (see .env.example)."
