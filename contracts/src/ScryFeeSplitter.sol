// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @title ScryFeeSplitter — every fun-layer fee flows through one posted split
/// @notice Games send their $SCRY fees (arena entries, chance-game rake,
///         sigil mints) to THIS address. Anyone may call distribute() at any
///         time; the current balance is pushed out by the posted basis-point
///         split — typically bank (ScryBank, the xSCRY flywheel) /
///         season-prize escrow / ops. The split is public state and every
///         change is an event, so the fee math is auditable end to end,
///         which is the SCRY-ECONOMY.md requirement.
///
///         The operator owns the split percentages — and ONLY the
///         percentages/recipients. There is no withdraw-everything owner
///         path: funds can only ever leave along the posted split. Rounding
///         dust goes to the last recipient so nothing sticks to the
///         contract.
contract ScryFeeSplitter {
    IERC20 public immutable scry;
    address public operator;

    struct Cut {
        address to;
        uint16 bps; // out of 10_000
    }

    Cut[] public cuts;

    event SplitSet(address[] to, uint16[] bps);
    event Distributed(uint256 amount);
    event OperatorTransferred(address indexed from, address indexed to);

    modifier onlyOperator() {
        require(msg.sender == operator, "not operator");
        _;
    }

    constructor(IERC20 _scry, address[] memory to, uint16[] memory bps) {
        scry = _scry;
        operator = msg.sender;
        _setSplit(to, bps);
    }

    /// Push the whole current balance out along the posted split. Anyone can
    /// call — the split is the only path funds can take.
    function distribute() external returns (uint256 amount) {
        amount = scry.balanceOf(address(this));
        require(amount > 0, "nothing to distribute");
        uint256 sent;
        uint256 n = cuts.length;
        for (uint256 i = 0; i < n; i++) {
            uint256 share = i == n - 1
                ? amount - sent // last recipient takes the rounding dust
                : (amount * cuts[i].bps) / 10_000;
            sent += share;
            require(scry.transfer(cuts[i].to, share), "transfer failed");
        }
        emit Distributed(amount);
    }

    /// Repost the split. Distributes any held balance FIRST, under the old
    /// posted split — fees collected under posted rules pay out under those
    /// rules; the new split only governs fees that arrive after it.
    function setSplit(address[] calldata to, uint16[] calldata bps) external onlyOperator {
        if (scry.balanceOf(address(this)) > 0) this.distribute();
        _setSplit(to, bps);
    }

    function transferOperator(address to) external onlyOperator {
        require(to != address(0), "zero");
        emit OperatorTransferred(operator, to);
        operator = to;
    }

    function splitLength() external view returns (uint256) {
        return cuts.length;
    }

    function _setSplit(address[] memory to, uint16[] memory bps) internal {
        require(to.length == bps.length && to.length > 0, "bad split");
        delete cuts;
        uint256 total;
        for (uint256 i = 0; i < to.length; i++) {
            require(to[i] != address(0), "zero recipient");
            total += bps[i];
            cuts.push(Cut(to[i], bps[i]));
        }
        require(total == 10_000, "bps must sum to 10000");
        // memory→calldata mismatch is fine for the event's abi encoding
        address[] memory a = to;
        uint16[] memory b = bps;
        emit SplitSet(a, b);
    }
}
