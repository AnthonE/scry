// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ScryReputation — soulbound market reputation
/// @notice Reputation must be NON-TRANSFERABLE or the incentive collapses:
///         you could buy a good name or sell a clean one, and a scammer could
///         wash a slashed record by moving wallets. So there is no transfer
///         path here at all — rep is a per-wallet score that only authorized
///         market contracts (the job board, the arbiter) may add to or slash.
///
///         Earned by outcomes (completed jobs, kept vows), slashed by adverse
///         rulings and broken bonds. It is the ecosystem's enforcement: below
///         `threshold`, a wallet can't take high-value jobs, so a bad actor
///         prices itself out and cannot escape the record.
///
///         This is DISTINCT from the meter's behavioral score (watched-vs-
///         unwatched, score-blind, never for sale). Rep is a market-history
///         record; the meter is an integrity measurement. Neither is
///         purchasable; keep them separate objects — never launder one into
///         the other.
contract ScryReputation {
    address public operator;
    uint256 public threshold; // rep needed for high-value jobs (public, posted)

    mapping(address => uint256) public rep;
    mapping(address => bool) public authorized; // market contracts that may mutate

    event Earned(address indexed who, uint256 amount, uint256 total, bytes32 reason);
    event Slashed(address indexed who, uint256 amount, uint256 total, bytes32 reason);
    event AuthoritySet(address indexed who, bool allowed);
    event ThresholdSet(uint256 threshold);
    event OperatorTransferred(address indexed from, address indexed to);

    modifier onlyOperator() {
        require(msg.sender == operator, "not operator");
        _;
    }

    modifier onlyAuthorized() {
        require(authorized[msg.sender], "not authorized");
        _;
    }

    constructor(uint256 _threshold) {
        operator = msg.sender;
        threshold = _threshold;
        emit ThresholdSet(_threshold);
    }

    /// Add rep for an outcome. Only market contracts, never a payment path —
    /// money never buys rep (that would be Bar Hadya for reputation).
    function earn(address who, uint256 amount, bytes32 reason) external onlyAuthorized {
        rep[who] += amount;
        emit Earned(who, amount, rep[who], reason);
    }

    /// Slash rep on an adverse ruling / broken bond. Saturating at zero.
    function slash(address who, uint256 amount, bytes32 reason) external onlyAuthorized {
        uint256 cur = rep[who];
        uint256 next = amount >= cur ? 0 : cur - amount;
        rep[who] = next;
        emit Slashed(who, cur - next, next, reason);
    }

    function meets(address who) external view returns (bool) {
        return rep[who] >= threshold;
    }

    function setAuthority(address who, bool allowed) external onlyOperator {
        authorized[who] = allowed;
        emit AuthoritySet(who, allowed);
    }

    function setThreshold(uint256 _threshold) external onlyOperator {
        threshold = _threshold;
        emit ThresholdSet(_threshold);
    }

    function transferOperator(address to) external onlyOperator {
        require(to != address(0), "zero");
        emit OperatorTransferred(operator, to);
        operator = to;
    }

    // Intentionally NO transfer / approve / mint-to-arbitrary functions.
    // Reputation is soulbound by construction: it can only be earned or
    // slashed by authorized market logic, never moved between wallets.
}
