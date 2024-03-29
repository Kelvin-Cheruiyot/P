import MetaTrader5 as mt5
import pandas as pd
import plotly.express as px

mt5.initialize()

symbol = 'EURUSD'
timeframe = mt5.TIMEFRAME_D1
start_pos = 0
num_bars = 1000

bars = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, num_bars)
df = pd.DataFrame(bars)[['time', 'open', 'high', 'low', 'close']]
df['time'] = pd.to_datetime(df['time'], unit='s')

df

fig = px.line(df, x='time', y='close', title='EURUSD - Close Prices')
 

rsi_period = 14

df['gain'] = (df['close'] - df['open']).apply(lambda x: x if x > 0 else 0)
df['loss'] = (df['close'] - df['open']).apply(lambda x: -x if x < 0 else 0)

df['ema_gain'] = df['gain'].ewm(span=rsi_period, min_periods=rsi_period).mean()
df['ema_loss'] = df['loss'].ewm(span=rsi_period, min_periods=rsi_period).mean()

df['rs'] = df['ema_gain'] / df['ema_loss']

df['rsi_14'] = 100 - (100 / (df['rs'] + 1))



fig_rsi = px.line(df, x='time', y='rsi_14', title='RSI Indicator')

overbought_level = 70
orversold_level = 30

fig_rsi.add_hline(y=overbought_level, opacity=0.5)
fig_rsi.add_hline(y=orversold_level, opacity=0.5)




atr_period = 14 
df['range'] = df['high'] - df['low']

df['atr_14'] = df['range'].rolling(atr_period).mean()



fig_atr = px.line(df, x='time', y='atr_14', title='ATR Indicator')



class Position:
    def __init__(self, open_datetime, open_price, order_type, volume, sl, tp):
        self.open_datetime = open_datetime
        self.open_price = open_price
        self.order_type = order_type
        self.volume = volume
        self.sl = sl
        self.tp = tp
        self.close_datetime = None
        self.close_price = None
        self.profit = None
        self.status = 'open'
        
    def close_position(self, close_datetime, close_price):
        self.close_datetime = close_datetime
        self.close_price = close_price
        self.profit = (self.close_price - self.open_price) * self.volume if self.order_type == 'buy' \
                                                                        else (self.open_price - self.close_price) * self.volume
        self.status = 'closed'
        
    def _asdict(self):
        return {
            'open_datetime': self.open_datetime,
            'open_price': self.open_price,
            'order_type': self.order_type,
            'volume': self.volume,
            'sl': self.sl,
            'tp': self.tp,
            'close_datetime': self.close_datetime,
            'close_price': self.close_price,
            'profit': self.profit,
            'status': self.status,
        }
        

# class Strategy defines trading logic and evaluates the backtest based on opened/closed positions
class Strategy:
    def __init__(self, df, starting_balance):
        self.starting_balance = starting_balance
        self.positions = []
        self.data = df
    
    # return backtest result
    def get_positions_df(self):
        df = pd.DataFrame([position._asdict() for position in self.positions])
        df['pnl'] = df['profit'].cumsum() + self.starting_balance
        return df
    
    # add Position class to list
    def add_position(self, position):
        self.positions.append(position)
        return True
    
    # close positions when stop loss or take profit is reached
    def close_tp_sl(self, data):
        for pos in self.positions:
                    if pos.status == 'open':
                        if (pos.sl >= data.close and pos.order_type == 'buy'):
                            pos.close_position(data.time, pos.sl)
                        elif (pos.sl <= data.close and pos.order_type == 'sell'):
                            pos.close_position(data.time, pos.sl)
                        elif (pos.tp <= data.close and pos.order_type == 'buy'):
                            pos.close_position(data.time, pos.tp)
                        elif (pos.tp >= data.close and pos.order_type == 'sell'):
                            pos.close_position(data.time, pos.tp)
                            
    # check for open positions
    def has_open_positions(self):
        for pos in self.positions:
            if pos.status == 'open':
                return True
        return False
    
    # strategy logic how positions should be opened/closed
    def logic(self, data):
        
        # if no position is open
        if not self.has_open_positions():
            
            # if RSI less then 30 -> BUY
            if data['rsi_14'] < 30:
                
                # Position variables
                open_datetime = data['time']
                open_price = data['close']
                order_type = 'buy'
                volume = 10000
                sl = open_price - 2 * data['atr_14']
                tp = open_price + 2 * data['atr_14']
                
                self.add_position(Position(open_datetime, open_price, order_type, volume, sl, tp))
            
            # if RSI greater than 70 -> SELL
            elif data['rsi_14'] > 70:
                
                # Position variables
                open_datetime = data['time']
                open_price = data['close']
                order_type = 'sell'
                volume = 10000
                sl = open_price + 2 * data['atr_14']
                tp = open_price - 2 * data['atr_14']
                
                self.add_position(Position(open_datetime, open_price, order_type, volume, sl, tp))
        
        
# logic
    def run(self):
        # data represents a moment in time while iterating through the backtest
        for i, data in self.data.iterrows():
            # close positions when stop loss or take profit is reached
            self.close_tp_sl(data)
            
            # strategy logic
            self.logic(data)
        
        return self.get_positions_df()

# %%
# preparing data for backtest
backtest_df = df[14:]  # removing NaN values
backtest_df

# %% [markdown]
# ## Running the backtest

# %%
# creating an instance of Strategy class
rsi_strategy = Strategy(backtest_df, 10000)

# running the backtest
backtest_result = rsi_strategy.run()

backtest_result

# %% [markdown]
# ## Visualizing the Backtest

# %%
# analysing closed positions only
backtest_result = backtest_result[backtest_result['status'] == 'closed']

# visualizing trades
fig_backtest = px.line(df, x='time', y=['close'], title='RSI Strategy - Trades')

# adding trades to plots
for i, position in backtest_result.iterrows():
    if position.status == 'closed':
        fig_backtest.add_shape(type="line",
            x0=position.open_datetime, y0=position.open_price, x1=position.close_datetime, y1=position.close_price,
            line=dict(
                color="green" if position.profit >= 0 else "red",
                width=3)
            )

fig_backtest

# %% [markdown]
# ## Plotting PnL

# %%
fig_pnl = px.line(backtest_result, x='close_datetime', y='pnl')
fig_pnl

# %%



