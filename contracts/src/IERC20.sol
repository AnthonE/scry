// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IERC20 — the minimal $SCRY surface the market contracts use.
/// @notice Shared so that a test (or any consumer) can import ScryJobBoard and
///         ScryInsurancePool together without a duplicate top-level `IERC20`
///         declaration colliding. The older fun-layer contracts each declare
///         IERC20 inline; the market spine uses this one canonical copy.
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}
