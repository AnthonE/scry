// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ScrySteleEdition.sol";

/// Deploy the stele-edition print shop to Robinhood Chain.
///   export PRIVATE_KEY=0x…
///   export SCRY_TOKEN=0xDa2a4b23459e9ca88183e990802be644AcA7C4B0   # $SCRY
///   export SCRY_FEE_SPLITTER=0x…    # deployed ScryFeeSplitter
///   export STELE_PRICE_WEI=5000000000000000000   # flat $SCRY per print (18-dec)
///   export SCRY_API_BASE=https://scry.moreright.xyz/api
///   forge script script/DeployScrySteleEdition.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
/// Flat price, immutable at deploy. The vow stays soulbound; the edition is a
/// transferable cosmetic print, $SCRY-in straight to the splitter.
contract DeployScrySteleEdition is Script {
    function run() external {
        vm.startBroadcast(vm.envUint("PRIVATE_KEY"));
        ScrySteleEdition ed = new ScrySteleEdition(
            IERC20(vm.envAddress("SCRY_TOKEN")),
            vm.envAddress("SCRY_FEE_SPLITTER"),
            vm.envUint("STELE_PRICE_WEI"),
            vm.envString("SCRY_API_BASE"));
        vm.stopBroadcast();
        console2.log("ScrySteleEdition", address(ed));
    }
}
