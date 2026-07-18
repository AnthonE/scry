// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/PlayToken.sol";
import "../src/ScryGarden.sol";
import "../src/ScryBurrow.sol";

/// Deploy the DeFi playground to Robinhood Chain — PLAY TOKENS ONLY.
///
///   export PRIVATE_KEY=0x…
///   forge script script/DeployPlayground.s.sol \
///     --rpc-url https://rpc.mainnet.chain.robinhood.com --broadcast
///
/// Deploys pGOLD + pTEARS (free faucets), the Garden (pGOLD/pTEARS pair),
/// and the Burrow (pGOLD collateral, pTEARS debt, garden-spot oracle).
/// The deployer faucets both tokens (1000 each) and seeds the garden
/// 500:500 plus donates 500 pTEARS of lendable depth to the Burrow so the
/// playground opens playable.
///
/// ⚠ Everything here is worthless by construction (infinite free faucets,
/// on-chain NOTICE strings). Never point real value at these contracts.
/// `forge test -vv` first, always.
contract DeployPlayground is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        PlayToken gold = new PlayToken("play gold", "pGOLD");
        PlayToken tears = new PlayToken("play tears", "pTEARS");
        ScryGarden garden = new ScryGarden(IERC20(address(gold)), IERC20(address(tears)));
        ScryBurrow burrow = new ScryBurrow(IERC20(address(gold)), IERC20(address(tears)),
                                           IGardenOracle(address(garden)));
        gold.faucet();
        tears.faucet();
        gold.approve(address(garden), type(uint256).max);
        tears.approve(address(garden), type(uint256).max);
        garden.addLiquidity(500e18, 500e18);
        tears.transfer(address(burrow), 500e18);
        vm.stopBroadcast();

        console2.log("pGOLD     ", address(gold));
        console2.log("pTEARS    ", address(tears));
        console2.log("ScryGarden", address(garden));
        console2.log("ScryBurrow", address(burrow));
    }
}
