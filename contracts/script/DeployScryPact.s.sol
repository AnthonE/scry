// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ScryPact.sol";

/// Deploy the Pact to Robinhood Chain. Permissionless, ownerless, free —
/// one broadcast and it belongs to every pair of parties.
///   export PRIVATE_KEY=0x…
///   forge script script/DeployScryPact.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
/// After deploy: set SCRY_PACT in keys.env so the meter's /pact surface links
/// each agreement to its on-chain register (PactProposed carries the full terms
/// + every role and obligation; PactComment/StatusAsserted carry the thread —
/// all explorer-readable).
contract DeployScryPact is Script {
    function run() external {
        vm.startBroadcast(vm.envUint("PRIVATE_KEY"));
        ScryPact pactContract = new ScryPact();
        vm.stopBroadcast();
        console2.log("ScryPact", address(pactContract));
    }
}
