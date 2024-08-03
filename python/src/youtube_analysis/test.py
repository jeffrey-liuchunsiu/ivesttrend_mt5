import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# Example data
dates = [
    datetime(2024, 7, 24),
    datetime(2024, 7, 25),
    datetime(2024, 7, 26),
    datetime(2024, 7, 27),
    datetime(2024, 7, 28),
    datetime(2024, 7, 29),
    datetime(2024, 7, 30)
]
elon_emotion_rate = [0, 100, 200, 50, 40, 60, 500]
tsla_close_price = [600, 620, 630, 610, 605, 615, 625]

fig, ax1 = plt.subplots()

color = 'tab:blue'
ax1.set_xlabel('Date')
ax1.set_ylabel('Elon Musk\'s Emotion Rate', color=color)
ax1.plot(dates, elon_emotion_rate, color=color)
ax1.tick_params(axis='y', labelcolor=color)

ax2 = ax1.twinx()
color = 'tab:red'
ax2.set_ylabel('TSLA Close Price', color=color)
ax2.plot(dates, tsla_close_price, color=color)
ax2.tick_params(axis='y', labelcolor=color)

fig.autofmt_xdate()
ax1.fmt_xdata = mdates.DateFormatter('%Y-%m-%d')
ax2.fmt_xdata = mdates.DateFormatter('%Y-%m-%d')

plt.title('Relationship between Elon Musk\'s Emotion Rate and TSLA Close Price')
plt.show()