// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

interface IGardenOracle {
    function spotPrice() external view returns (uint256); // token0 in token1, 1e18
}

/// @title ScryBurrow — the playground's toy lending pool (liquidations are content)
/// @notice Deposit pGOLD collateral, borrow pTEARS against it, keep your
///         health factor above water — or get liquidated in public. Sworn
///         agents vow a management strategy ("never borrow past 60% LTV")
///         and the record shows whether they kept it when the price moved.
///
///         Deliberate simplifications, all safe because every token here is
///         a free-faucet PLAY token worth nothing:
///         - The lendable pTEARS is donated (faucet + transfer) — no lender
///           shares, no deposit APY, nothing to farm.
///         - The oracle is the Garden's raw spot price, which is trivially
///           manipulable. Hunting liquidations by shoving the pool IS the
///           game — at zero real stakes it's a sandbox for exactly the
///           attacks that cost real protocols nine figures.
///         Never point real value at this. NOTICE says so on-chain.
contract ScryBurrow {
    string public constant NOTICE =
        "toy lending pool - play tokens only, manipulable oracle by design, scry playground";

    IERC20 public immutable collateralToken; // garden token0 (pGOLD)
    IERC20 public immutable debtToken;       // garden token1 (pTEARS)
    IGardenOracle public immutable oracle;   // the garden itself

    uint256 public constant BORROW_LTV_BPS = 6000;  // borrow up to 60%
    uint256 public constant LIQ_LTV_BPS = 7500;     // liquidatable past 75%
    uint256 public constant LIQ_BONUS_BPS = 1000;   // liquidator takes +10%
    uint256 public constant RATE_PER_SEC = 3_170_979_198; // ~10% APR on 1e18

    uint256 public borrowIndex = 1e18;
    uint64 public lastAccrue;

    mapping(address => uint256) public collateral;   // pGOLD posted
    mapping(address => uint256) public debtShares;   // debt / index at borrow time

    event Deposit(address indexed who, uint256 amount);
    event Withdraw(address indexed who, uint256 amount);
    event Borrow(address indexed who, uint256 amount);
    event Repay(address indexed who, uint256 amount);
    event Liquidate(address indexed borrower, address indexed liquidator,
                    uint256 debtRepaid, uint256 collateralSeized);

    constructor(IERC20 _collateral, IERC20 _debt, IGardenOracle _oracle) {
        collateralToken = _collateral;
        debtToken = _debt;
        oracle = _oracle;
        lastAccrue = uint64(block.timestamp);
    }

    // ── interest ────────────────────────────────────────────────────────────
    function accrue() public {
        uint256 dt = block.timestamp - lastAccrue;
        if (dt > 0) {
            borrowIndex += (borrowIndex * RATE_PER_SEC * dt) / 1e18;
            lastAccrue = uint64(block.timestamp);
        }
    }

    function debtOf(address who) public view returns (uint256) {
        uint256 idx = borrowIndex +
            (borrowIndex * RATE_PER_SEC * (block.timestamp - lastAccrue)) / 1e18;
        return (debtShares[who] * idx) / 1e18;
    }

    /// 1e18 = at the liquidation line; below = liquidatable. type(uint).max if no debt.
    function healthFactor(address who) public view returns (uint256) {
        uint256 debt = debtOf(who);
        if (debt == 0) return type(uint256).max;
        uint256 collValue = (collateral[who] * oracle.spotPrice()) / 1e18; // in debt token
        return (collValue * LIQ_LTV_BPS) / 10_000 * 1e18 / debt;
    }

    // ── borrower surface ────────────────────────────────────────────────────
    function depositCollateral(uint256 amount) external {
        accrue();
        require(amount > 0, "zero");
        collateral[msg.sender] += amount;
        require(collateralToken.transferFrom(msg.sender, address(this), amount), "in");
        emit Deposit(msg.sender, amount);
    }

    function withdrawCollateral(uint256 amount) external {
        accrue();
        require(amount > 0 && collateral[msg.sender] >= amount, "bad amount");
        collateral[msg.sender] -= amount;
        require(_withinBorrowLtv(msg.sender), "would exceed borrow LTV");
        require(collateralToken.transfer(msg.sender, amount), "out");
        emit Withdraw(msg.sender, amount);
    }

    function borrow(uint256 amount) external {
        accrue();
        require(amount > 0, "zero");
        debtShares[msg.sender] += (amount * 1e18) / borrowIndex;
        require(_withinBorrowLtv(msg.sender), "exceeds borrow LTV");
        require(debtToken.transfer(msg.sender, amount), "pool dry - faucet+donate pTEARS");
        emit Borrow(msg.sender, amount);
    }

    function repay(uint256 amount) external {
        accrue();
        uint256 debt = (debtShares[msg.sender] * borrowIndex) / 1e18;
        uint256 pay = amount > debt ? debt : amount;
        require(pay > 0, "no debt");
        debtShares[msg.sender] -= (pay * 1e18) / borrowIndex;
        require(debtToken.transferFrom(msg.sender, address(this), pay), "in");
        emit Repay(msg.sender, pay);
    }

    // ── the content ─────────────────────────────────────────────────────────
    /// Anyone repays an underwater borrower's full debt and seizes collateral
    /// worth debt × (1 + bonus) at the oracle price (capped at what's there).
    /// KNOWN LIMIT (deliberate, play-tokens-only): there is no close factor or
    /// partial path — the liquidator always fronts the FULL debt. Once a
    /// position is underwater past the bonus (collateral value < debt × 1.1),
    /// liquidating loses money and nobody calls: the position sits as bad debt.
    /// That failure mode is part of the toy; never point real value at this.
    function liquidate(address borrower) external {
        accrue();
        require(healthFactor(borrower) < 1e18, "healthy");
        uint256 debt = (debtShares[borrower] * borrowIndex) / 1e18;
        uint256 price = oracle.spotPrice();
        uint256 seize = (debt * (10_000 + LIQ_BONUS_BPS)) / 10_000 * 1e18 / price;
        if (seize > collateral[borrower]) seize = collateral[borrower];
        debtShares[borrower] = 0;
        collateral[borrower] -= seize;
        require(debtToken.transferFrom(msg.sender, address(this), debt), "repay in");
        require(collateralToken.transfer(msg.sender, seize), "seize out");
        emit Liquidate(borrower, msg.sender, debt, seize);
    }

    function _withinBorrowLtv(address who) internal view returns (bool) {
        uint256 debt = (debtShares[who] * borrowIndex) / 1e18;
        if (debt == 0) return true;
        uint256 collValue = (collateral[who] * oracle.spotPrice()) / 1e18;
        return debt <= (collValue * BORROW_LTV_BPS) / 10_000;
    }
}
