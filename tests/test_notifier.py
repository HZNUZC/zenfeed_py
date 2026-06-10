import asyncio
from email.message import EmailMessage
from typing import TypedDict

import pytest
from zenfeed import Feed
from zenfeed.config import ContentTemplate, EmailChannel as EmailChannelConfig
from zenfeed.config import EmailContent, ReceiverConfig
from zenfeed.notifier import Channel, EmailChannel, Receiver


class SentEmail(TypedDict, total=False):
    message: EmailMessage
    hostname: str
    username: str
    password: str
    port: int


class RecordingChannel(Channel):
    def __init__(self) -> None:
        self.sent = []

    async def send(self, feed_slice: list[Feed]) -> None:
        self.sent.append(feed_slice)


class FakeChannels:
    def __init__(self, channel: Channel) -> None:
        self.channel = channel

    def get(self, name: str) -> Channel | None:
        return self.channel


def _feed(title: str, link: str = "https://example.invalid/feed") -> Feed:
    return Feed.from_dict({"title": title, "link": link}, 1)


def test_build_content_renders_one_item_per_feed() -> None:
    channel = RecordingChannel()
    template = ContentTemplate(item_template="{title} <{link}>", separator="\n")

    content = channel._build_content(
        template,
        [
            _feed("first", "https://example.invalid/1"),
            _feed("second", "https://example.invalid/2"),
        ],
    )

    assert content == (
        "first <https://example.invalid/1>\n"
        "second <https://example.invalid/2>"
    )


def test_receiver_slices_feeds_by_configured_slice_size() -> None:
    channel = RecordingChannel()
    receiver = Receiver(
        ReceiverConfig(name="daily", channel="hook", slice_size=2),
        FakeChannels(channel),  # type: ignore
    )
    feeds = [_feed(str(i)) for i in range(5)]

    slices = receiver._feed_slice(feeds)

    assert slices == [feeds[0:2], feeds[2:4], feeds[4:5]]


def test_receiver_sends_each_slice_to_channel() -> None:
    channel = RecordingChannel()
    receiver = Receiver(
        ReceiverConfig(name="daily", channel="hook", slice_size=2),
        FakeChannels(channel),  # type: ignore
    )
    feeds = [_feed(str(i)) for i in range(3)]

    asyncio.run(receiver.send_channel(feeds))

    assert channel.sent == [feeds[0:2], feeds[2:3]]


def test_email_channel_builds_message_and_uses_smtp_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: SentEmail = {}

    async def fake_send(
        message: EmailMessage,
        hostname: str,
        username: str,
        password: str,
        port: int,
        **kwargs: object,
    ) -> None:
        sent["message"] = message
        sent["hostname"] = hostname
        sent["username"] = username
        sent["password"] = password
        sent["port"] = port

    monkeypatch.setattr("zenfeed.notifier.aiosmtplib.send", fake_send)

    channel = EmailChannel(
        EmailChannelConfig(
            name="smtp",
            url="smtp.example.invalid",
            port=465,
            user="robot@example.invalid",
            passwd="password",
            mail_meta=[
                "from@example.invalid",
                "to-one@example.invalid",
                "to-two@example.invalid",
            ],
            mail_content_t=EmailContent(
                subject="Daily feeds",
                content=ContentTemplate(
                    item_template="{title}",
                    separator="\n",
                ),
            ),
        )
    )

    asyncio.run(channel.send([_feed("first"), _feed("second")]))

    message = sent["message"]
    assert message["From"] == "from@example.invalid"
    assert message["To"] == "to-one@example.invalid, to-two@example.invalid"
    assert message["Subject"] == "Daily feeds"
    assert message.get_content() == "first\nsecond\n"
    assert sent["hostname"] == "smtp.example.invalid"
    assert sent["username"] == "robot@example.invalid"
    assert sent["password"] == "password"
    assert sent["port"] == 465
