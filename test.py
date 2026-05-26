from zenfeed import Labels, Feed
from datetime import datetime

l_dict = {'title': 'Hello World', 'source': 'hackernews', 'content': 'This is a test article', 'link': 'https://example.com', 'type': 'article', 'pub_time': '2026-05-25'}

time = int(datetime.now().timestamp())

f = Feed(time)

f2 = Feed.from_dict(l_dict, time)

f.set_labels(l_dict)

print(f.time)
print(f.get_labels())