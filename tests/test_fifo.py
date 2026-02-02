from hledger_lots import fifo

from . import lots_data


class TestGetLots:
    def test_only_buying(self):
        assert (
            fifo.get_lots(lots_data.txns_only_buying, check=False)
            == lots_data.txns_only_buying
        )

    def test_never_zero(self):
        assert (
            fifo.get_lots(lots_data.txns_qtty_never_zero, check=False)
            == lots_data.expected_qtty_never_zero
        )

    def test_qtty_reach_zero(self):
        assert (
            fifo.get_lots(lots_data.txns_qtty_reaches_zero, check=False)
            == lots_data.expected_qtty_reaches_zero
        )


class TestGetSellLots:
    def test_sell_all(self):
        sell_lots = fifo.get_sell_lots(
            lots_data.txns_qtty_reaches_zero,
            sell_date="2022-02-01",
            sell_qtty=5,
            check=False,
        )
        assert sell_lots == lots_data.expected_qtty_reaches_zero_sell_all

    def test_sell_some(self):
        sell_lots = fifo.get_sell_lots(
            lots_data.txns_qtty_never_zero,
            sell_date="2022-02-01",
            sell_qtty=11,
            check=False,
        )
        assert sell_lots == lots_data.expected_qtty_never_zero_sell_some


class TestTxn2Hl:
    txns = lots_data.expected_qtty_reaches_zero_sell_all
    date = "2022-02-01"
    cash_account = "Bank"
    revenue_account = "Revenue"

    def test_txn2hl_profit(self):
        cur = "USD"
        test = fifo.txn2hl(
            self.txns, self.date, cur, self.cash_account, self.revenue_account, 160)

        expected = """2022-02-01 Sold USD  ; cost_method:fifo
    ; commodity:USD, qtty:5.00, price:32.00
    ; avg_cost:26.0000, total_cost:130.00, xirr:61.42% annual percent rate 30/360US
    Bank                   160.00 USD
    Acct1      -2.00 USD @@ 70.00 USD  ; buy_date:2022-01-12, base_cur:USD
    Acct1      -3.00 USD @@ 60.00 USD  ; buy_date:2022-01-14, base_cur:USD
    Revenue                -30.00 USD

"""

        assert test == expected

    def test_txn2hl_loss(self):
        cur = "USD"
        test = fifo.txn2hl(
            self.txns, self.date, cur, self.cash_account, self.revenue_account, 80
        )

        expected = """2022-02-01 Sold USD  ; cost_method:fifo
    ; commodity:USD, qtty:5.00, price:16.00
    ; avg_cost:26.0000, total_cost:130.00, xirr:-1.00% annual percent rate 30/360US
    Bank                    80.00 USD
    Acct1      -2.00 USD @@ 70.00 USD  ; buy_date:2022-01-12, base_cur:USD
    Acct1      -3.00 USD @@ 60.00 USD  ; buy_date:2022-01-14, base_cur:USD
    Revenue                 50.00 USD

"""

        assert test == expected

    def test_decimal_precision(self):
        """Test that FIFO calculation doesn't introduce floating point errors."""
        from hledger_lots.types import AdjustedTxn
        
        # Simulate the real-world scenario from the bug report
        txns = [
            AdjustedTxn("2025-11-30", 118.8450, "EUR", 0.08389078, "Assets:Crypto:SOL"),
            AdjustedTxn("2025-12-26", 106.4252, "EUR", 0.04688739, "Assets:Crypto:SOL"),
            AdjustedTxn("2025-12-30", 106.1429, "EUR", 0.04701208, "Assets:Crypto:SOL"),
            AdjustedTxn("2026-01-04", 115.2763, "EUR", 0.08651568, "Assets:Crypto:SOL"),
        ]
        
        # Sell exactly 0.20271703 SOL
        sell_qtty = 0.20271703
        sell_lots = fifo.get_sell_lots(txns, "2026-01-17", sell_qtty, check=False)
        
        # Verify we got 4 lots
        assert len(sell_lots) == 4
        
        # The last lot should have exactly 0.02492678 (calculated precisely)
        # Not 0.024926779999999996 (floating point error)
        expected_last_qtty = 0.02492678
        actual_last_qtty = sell_lots[3].qtty
        
        # They should be equal within reasonable precision
        assert abs(actual_last_qtty - expected_last_qtty) < 1e-10
        
        # Verify total equals sell quantity
        total_qtty = sum(lot.qtty for lot in sell_lots)
        assert abs(total_qtty - sell_qtty) < 1e-10

