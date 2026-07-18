// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/ScryReputation.sol";
import "../src/ScryInsurancePool.sol";
import "../src/ScryJobBoard.sol";
import "../src/IScryArbiter.sol";

/// Deploy the agent-labor market spine to Robinhood Chain mainnet.
///
///   export PRIVATE_KEY=0x…
///   export SCRY_TOKEN=0xDa2a4b23459e9ca88183e990802be644AcA7C4B0
///   export SCRY_FEE_SPLITTER=0x…     # existing ScryFeeSplitter
///   export SCRY_ARBITER=0x…          # a deployed IScryArbiter (panel)
///   export SCRY_REP_THRESHOLD=50
///   export SCRY_MAX_PAYOUT=1000000000000000000000
///   forge script script/DeployScryMarket.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
///
/// Order: reputation + pool first, then the board pointing at both, then wire
/// the board as an authorized rep-mutator and pool claimant. The board is the
/// ONLY contract allowed to move rep or claim from the pool.
///
/// ⚠ Broadcast is a deliberate human step — real gas, real custody of escrow.
/// `forge test -vv` first, and sanity-check the arbiter is a real panel (not a
/// single oracle) before pointing money at it.
contract DeployScryMarket is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        IERC20 scry = IERC20(vm.envAddress("SCRY_TOKEN"));
        address feeSplitter = vm.envAddress("SCRY_FEE_SPLITTER");
        IScryArbiter arbiter = IScryArbiter(vm.envAddress("SCRY_ARBITER"));
        uint256 threshold = vm.envOr("SCRY_REP_THRESHOLD", uint256(50));
        uint256 maxPayout = vm.envOr("SCRY_MAX_PAYOUT", uint256(1000e18));

        vm.startBroadcast(pk);
        ScryReputation reputation = new ScryReputation(threshold);
        ScryInsurancePool pool = new ScryInsurancePool(scry, maxPayout);
        ScryJobBoard board = new ScryJobBoard(
            scry, IReputation(address(reputation)), IInsurancePool(address(pool)), feeSplitter, arbiter);

        reputation.setAuthority(address(board), true); // only the board moves rep
        pool.setClaimant(address(board), true); // only the board claims coverage
        vm.stopBroadcast();

        console.log("ScryReputation", address(reputation));
        console.log("ScryInsurancePool", address(pool));
        console.log("ScryJobBoard", address(board));
    }
}
