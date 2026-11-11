from ytrec.podcast_whitelist import load_podcast_channels, MIN_DURATION
from ytrec.core import language_gate

def test_whitelist_has_named_shows_and_duration():
    payload, channels, minimum = load_podcast_channels()
    names = {channel['name'] for channel in channels}
    for required in ('Dwarkesh', 'Lex Fridman', 'Acquired', "Lenny's Podcast", '20VC', 'Latent Space', 'No Priors', '硅谷101', '晚点 LatePost', '乱翻书'):
        assert required in names
    assert minimum >= 1500

def test_short_episode_would_be_dropped():
    short = dict(title='x', default_audio_language='en', duration_seconds=1499)
    assert language_gate(short)
    assert short['duration_seconds'] < MIN_DURATION


def test_zhang_xiaojun_label_is_correct():
    payload, channels, minimum = load_podcast_channels()
    names = {channel['name'] for channel in channels}
    assert '张小玺' not in names
    xiaojun = next(channel for channel in channels if channel['name'] == '张小珺')
    assert xiaojun['handle'] == 'xiaojunpodcast'
    assert xiaojun['youtube_channel_id'] == 'UC3Sv1JuKpbOx3csUO8FAo5g'
    assert xiaojun['youtube_title'] == 'Zhang Xiaojun Podcast'
