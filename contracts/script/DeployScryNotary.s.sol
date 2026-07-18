// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ScryNotary.sol";

/// Deploy the Notary to Robinhood Chain. Permissionless, ownerless, free —
/// one broadcast and it belongs to everyone.
///   export PRIVATE_KEY=0x…
///   forge script script/DeployScryNotary.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
/// After deploy: set SCRY_NOTARY in keys.env so the anchor worker posts the
/// daily augury seed commit here (label "augury seed commit YYYY-MM-DD") —
/// the commit-reveal stream becomes an explorer-readable public beacon.
contract DeployScryNotary is Script {
    function run() external {
        vm.startBroadcast(vm.envUint("PRIVATE_KEY"));
        ScryNotary notary = new ScryNotary();
        vm.stopBroadcast();
        console2.log("ScryNotary", address(notary));
    }
}
