// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";

/// ERC-8004 Trustless Agents — register scry's identity in the ecosystem's
/// trust layer, so counterparties resolve the pubkey + agent card from the
/// registry instead of pinning an off-chain blob.
///
///   export PRIVATE_KEY=0x…
///   export ERC8004_IDENTITY_REGISTRY=0x…   # canonical mainnet registry —
///                                          # VERIFY from the EIP-8004 spec /
///                                          # official deployments list before
///                                          # broadcasting; do NOT guess
///   export SCRY_AGENT_DOMAIN=scry.moreright.xyz
///   forge script script/RegisterERC8004.s.sol --rpc-url $ETH_RPC --broadcast
///
/// The registry resolves agentDomain -> /.well-known/agent.json (already
/// served), which carries the Ed25519 pubkey + skills + payment rails.
/// ⚠ Ethereum mainnet gas; one-time; operator-gated like every broadcast.
interface IIdentityRegistry {
    function newAgent(string calldata agentDomain, address agentAddress)
        external returns (uint256 agentId);
}

contract RegisterERC8004 is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address registry = vm.envAddress("ERC8004_IDENTITY_REGISTRY");
        string memory domain = vm.envOr("SCRY_AGENT_DOMAIN", string("scry.moreright.xyz"));
        vm.startBroadcast(pk);
        uint256 id = IIdentityRegistry(registry).newAgent(domain, vm.addr(pk));
        vm.stopBroadcast();
        console2.log("ERC-8004 agentId", id);
    }
}
