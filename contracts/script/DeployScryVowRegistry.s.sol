// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ScryVowRegistry.sol";

/// Deploy to Robinhood Chain mainnet (eip155:4663).
///
///   export PRIVATE_KEY=0x…      # DEPLOYER (already funded for facilitator gas)
///   export SCRY_ANCHOR_ORACLE=0x…  # the wallet the anchor worker sends from
///                                  # (defaults to the deployer)
///   forge script script/DeployScryVowRegistry.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
///
/// ⚠ Broadcast is a deliberate human step — costs real gas, creates a real
/// permanent registry. Run the tests first: `forge test -vv`.
contract DeployScryVowRegistry is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address oracle = vm.envOr("SCRY_ANCHOR_ORACLE", vm.addr(pk));
        vm.startBroadcast(pk);
        ScryVowRegistry reg = new ScryVowRegistry(oracle);
        vm.stopBroadcast();
        console2.log("ScryVowRegistry deployed:", address(reg));
        console2.log("anchor oracle:", oracle);
    }
}
