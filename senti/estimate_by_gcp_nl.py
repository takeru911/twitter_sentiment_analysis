import json
import time
from datetime import datetime as dt
from util import logger as Logger
from google.cloud import language
from google.cloud.language_v1 import enums
from google.cloud.language_v1 import types

logger = Logger.Logger(__name__)


def estimate_sentiment(client, sentence):
    document = types.Document(
        content=sentence,
        type=enums.Document.Type.PLAIN_TEXT,
        language="ja_JP"
    )
    sentiment = client.analyze_sentiment(document=document).document_sentiment
    logger.info("score: {}, magnitude: {}".format(sentiment.score, sentiment.magnitude))

    return sentiment


def build_client():
    return language.LanguageServiceClient()


client = build_client()
with open("../zombie_2018-11-30.json.senti", encoding="utf8") as f:
    lines = f.readlines()
    result_set = []
    try:
        for line in lines:
            tweet = json.loads(line)
            text = tweet["text"]
            self_score = tweet["score"]
            created_at_raw = tweet["created_at"]
            created_at = dt.strptime(created_at_raw, "%Y-%m-%d %H:%M:%S")
            limit = dt.strptime("2018-11-30 01:00:00", "%Y-%m-%d %H:%M:%S")

            if created_at > limit:
                continue
            sentiment = estimate_sentiment(client, text)
            gcp_score = sentiment.score
            gcp_magnitude = sentiment.magnitude
            tweet["gcp_score"] = gcp_score
            tweet["gcp_magnitude"] = gcp_magnitude
            result_set.append(tweet)
    except:
        import traceback
        logger.error(traceback.print_exc())

    result_file = open("../zonbie_2018-11-30.json.gcp_senti", "a", encoding="utf8")
    for r in result_set:
        json.dump(r, result_file, ensure_ascii=False)
        result_file.write('\n')
