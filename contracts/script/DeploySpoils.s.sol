// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/SpoilsToken.sol";
import "../src/ScryGarden.sol";

/// Deploy the spoils pair (OBOL + MYRRH) to Robinhood Chain — the CAPPED
/// play tokens the Barrow mints and the Agora burns.
///
///   export PRIVATE_KEY=0x…
///   # optional: pair the spoils against $SCRY in fresh Gardens
///   export SCRY_TOKEN=0xDa2a4b23459e9ca88183e990802be644AcA7C4B0
///   forge script script/DeploySpoils.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
///
/// Caps mirror the meter's off-chain spoils ledger (meter/tokens.py):
/// 1,000,000 OBOL · 250,000 MYRRH, cumulative-forever. The deployer starts
/// as minter and should rotate to the merkle distributor once the claim
/// contract exists (`setMinter`). Mint happens ONLY against the public game
/// ledger — deploy does not pre-mine anything.
///
/// ⚠ Unlike the DeployPlayground faucet pair, THESE tokens may face $SCRY
/// in a Garden — that is the point of the cap. The reverse warning stands:
/// never pool the free-faucet pGOLD/pTEARS against $SCRY or any valued
/// token; the faucet drains the real side. `forge test -vv` first, always.
contract DeploySpoils is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);
        vm.startBroadcast(pk);
        SpoilsToken obol = new SpoilsToken("obol", "OBOL", 1_000_000e18, deployer);
        SpoilsToken myrrh = new SpoilsToken("myrrh", "MYRRH", 250_000e18, deployer);
        address scry = vm.envOr("SCRY_TOKEN", address(0));
        if (scry != address(0)) {
            new ScryGarden(IERC20(address(obol)), IERC20(scry));
            new ScryGarden(IERC20(address(myrrh)), IERC20(scry));
        }
        vm.stopBroadcast();
        console2.log("OBOL", address(obol));
        console2.log("MYRRH", address(myrrh));
    }
}
