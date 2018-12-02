import configparser
import twitter
import datetime
import json
from util import logger
from datetime import datetime as dt
from time import sleep



class Twitter(object):

    def __init__(self, credential_path):
        self.logger = logger.Logger(name=__name__)
        self.twitter_client = self.build_twitter_client(credential_path)

    def build_twitter_client(self, credential_path):
        config = configparser.ConfigParser()
        config.read(credential_path)

        consumer_key = config["twitter_credential"]["CONSUMER_KEY"]
        consumer_secret = config["twitter_credential"]["CONSUMER_SECRET"]
        access_token_key = config["twitter_credential"]["ACCESS_TOKEN_KEY"]
        access_token_secret = config["twitter_credential"]["ACCESS_TOKEN_SECRET"]
        client = twitter.Api(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token_key=access_token_key,
            access_token_secret=access_token_secret
        )
        self.logger.info("build twitter api client")
        return client

    def search_by_hash_tag(self, hash_tag, count=100, max_id=None, until=None):
        raw_query = "q={hash_tag} -RT%20&result_type=recent&count={count}&locale=ja&lang=ja&include_entities=false".format(hash_tag=hash_tag, count=count)
        if max_id is not None:
            raw_query = raw_query + "&max_id={max_id}".format(max_id=max_id)
        if until is not None:
            raw_query = raw_query + "&until={until}".format(until=until)
        self.logger.info("raw_query:{}".format(raw_query))
        search_result = self.twitter_client.GetSearch(
            raw_query=raw_query
        )
        return search_result


def format_tweet(tweet):
    # 日時のformatを直して、JSTに変換
    created_at = dt.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y") \
                 + datetime.timedelta(hours=9)

    return {
        "id": tweet.id,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "text": tweet.text
    }


def get_tweet(client, query, date, max_id=None):
    result_set = []
    try:
        while True:
            print(max_id)
            result = client.search_by_hash_tag(query, max_id=max_id)
            # 最も古いtweetのidから1引いたものを次のapi callに利用
            max_id = result[-1].id - 1
            format_result = []
            is_over = False
            for r in result:
                format_result.append(format_tweet(r))
            for r in format_result:
                created_at = dt.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
                text = r["text"]
                limit = dt.strptime(date, "%Y-%m-%d %H:%M:%S")
                if created_at < limit:
                    is_over = True
                else:
                    if query in text or query.upper() in text:
                        result_set.append(r)
            print(result_set[-1]["created_at"])
            if is_over:
                break
            sleep(1)
    except twitter.error.TwitterError:
        print("twitter.error.TwitterError")
        return result_set
    return result_set


date = "2018-11-28"
anime = "sao"
word = 'sao'
max_id = 1067795250020737024

if max_id is not None:
    max_id = max_id - 1
client = Twitter("../twitter.credential")
date_result = get_tweet(client, word, "{} 00:00:00".format(date), max_id=max_id)
f = open("../{}_{}.json".format(anime, date), "a", encoding="utf-8")
for r in date_result:
    json.dump(r, f, ensure_ascii=False)
    f.write('\n')
