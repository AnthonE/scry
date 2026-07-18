// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ScryBank.sol";
import "../src/ScryFeeSplitter.sol";
import "../src/ScryHarvest.sol";

/// Deploy the fun-layer economy spine to Robinhood Chain mainnet.
///
///   export PRIVATE_KEY=0x…          # operator deployer
///   export SCRY_TOKEN=0xDa2a4b23459e9ca88183e990802be644AcA7C4B0
///   export SCRY_OPS=0x…             # ops fee sink (defaults to deployer)
///   forge script script/DeployScryEconomy.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
///
/// Order matters: bank first (the splitter needs its address), then harvest
/// (the prize/harvest escrow), then the splitter pointing at both. Default
/// split — bank 50% / harvest escrow 30% / ops 20% — is a STARTING POST,
/// operator-changeable on-chain via setSplit (held fees always pay out under
/// the split they were collected under).
///
/// ⚠ Broadcast is a deliberate human step — costs real gas, creates real
/// operator obligations (posted split, claimable roots). `forge test -vv`
/// first, always.
contract DeployScryEconomy is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        IERC20 scry = IERC20(vm.envAddress("SCRY_TOKEN"));
        address ops = vm.envOr("SCRY_OPS", vm.addr(pk));

        vm.startBroadcast(pk);
        ScryBank bank = new ScryBank(scry);
        ScryHarvest harvest = new ScryHarvest(scry);

        address[] memory to = new address[](3);
        uint16[] memory bps = new uint16[](3);
        to[0] = address(bank);    bps[0] = 5000;
        to[1] = address(harvest); bps[1] = 3000;
        to[2] = ops;              bps[2] = 2000;
        ScryFeeSplitter splitter = new ScryFeeSplitter(scry, to, bps);
        vm.stopBroadcast();

        console2.log("ScryBank      ", address(bank));
        console2.log("ScryHarvest   ", address(harvest));
        console2.log("ScryFeeSplitter", address(splitter));
    }
}
