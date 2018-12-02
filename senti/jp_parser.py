import MeCab
import CaboCha
import pandas as pd
from collections import namedtuple


class JpParser:
    """
    return parsed data with Mecab
    """
    POS_DIC = {
        'BOS/EOS': 'EOS', # end of sentense
        '形容詞' : 'ADJ',
        '副詞'   : 'ADV',
        '名詞'   : 'NOUN',
        '動詞'   : 'VERB',
        '助動詞' : 'AUX',
        '助詞'   : 'PART',
        '連体詞' : 'ADJ', # Japanese-specific POS
        '感動詞' : 'INTJ',
        '接続詞' : 'CONJ',
        '*'      : 'X',
    }

    def __init__(self, * ,sys_dic_path=''):
        tagger = MeCab.Tagger()
        tagger.parse('') # for UnicodeDecodeError
        self._tagger = tagger
        self._parser = CaboCha.Parser()
        self.senti_db = self.get_senti_db()

    def get_senti_db(self):
        pn_m3 = pd.read_csv("../pn.csv.m3.120408.trim", header=None, names=("word", "type"), sep="\t")
        pn_wago = pd.read_csv("../wago.121808.pn", header=None, names=("word", "type"), sep="\t")

        senti_db = pd.concat([pn_m3, pn_wago])
        return senti_db

    def get_word_pn(self, word):
        word_pn = self.senti_db[self.senti_db["word"] == word]["type"]

        if len(word_pn) == 0:
            return 0

        # 一度listにcastしないと、エラーでてしまう、うーん
        if list(word_pn)[0] == "n":
            return -1
        elif list(word_pn)[0] == "p":
            return 1
        else:
            return 0

    def search_politely_dict(self, words):
        politely_dict = dict()
        for w in words:
            res = self.get_word_pn(w)
            politely_dict.update({w: res})

        return politely_dict

    def apply_politely_reverse_rule_for_senti_analisys(self, i, tokens, scores, sentence):
        reverse_multiwords = [
            # headword,N-gram,apply_type
            ['の で は ない',       3, 'own'],
            ['わけ で は ない',     3, 'own'],
            ['わけ に は いく ない',4, 'src'],
        ]
        reverse_words = [
            # headword,pos,apply_type
            ['ない', 'AUX', 'own'],
            ['ぬ',   'AUX', 'own'],
            ['ない', 'ADJ', 'own'],
        ]
        apply_type = ''
        # detect politely-reverse word ( like a 'not' )
        # -------------------------------------------------------------------
        for r in reverse_words:
            if tokens[i].base_form==r[0] and tokens[i].pos==r[1]:
                apply_type = r[2]
        for r in reverse_multiwords:
            if i >= r[1]:
                multi_words = [ x.base_form.lower() for x in tokens if i-r[1] <= x.idx <= i]
                if ' '.join(multi_words) == r[0]:
                    apply_type = r[2]
        # apply for score
        # -------------------------------------------------------------------
        if apply_type!='':
            chunk = self.get_chunk_data(sentence)
            for j in range(0,len(chunk)):
                c = chunk[j]
                if c.token_idx <= i <= c.token_idx+c.token_size-1:
                    if apply_type=='own':
                        start_idx, end_idx = c.token_idx, (c.token_idx+c.token_size)
                    elif apply_type=='src':
                        sc = chunk[c.src_idx[-1]]
                        start_idx, end_idx = sc.token_idx, (sc.token_idx+sc.token_size)
                    # elif apply_type=='depend':
                    max_score_of_reverse = max(scores[start_idx:end_idx])
                    del scores[start_idx:end_idx]
                    scores.append(-1*int(max_score_of_reverse))
                    scores.extend([0 for i in range(end_idx-start_idx-1)])
                    break
        return scores

    def get_chunk_data(self, sentence):
        tree = self._parser.parse(sentence)
        tokens = self.tokenize(sentence)
        chunk_data = list()
        for i in range(0, tree.chunk_size()):
            chunk = namedtuple('Chunk', 'tokens, head_token, chunk_idx, depend_idx, src_idx, head_idx, func_idx,\
                                token_size, token_idx, feature_size, score, additional_info')
            c = tree.chunk(i)
            c_tokens = list()
            for j in range(c.token_pos, c.token_pos+c.token_size):
                c_tokens.append(tokens[j])
            chunk.tokens       = c_tokens
            chunk.head_token   = c_tokens[c.head_pos] # 主辞のtoken
            chunk.chunk_idx    = i                    # chunk_index
            chunk.depend_idx   = c.link               # dependecy chunk index
            chunk.src_idx      = list()               # source chunk (recieve chunk) index
            chunk.head_idx     = c.head_pos           # 主辞のindex
            chunk.func_idx     = c.func_pos           # 機能語のindex
            chunk.token_size   = c.token_size
            chunk.token_idx    = c.token_pos          # chunk先頭tokenのindex
            chunk.feature_size = c.feature_list_size
            chunk.score        = c.score
            chunk.additional_info = c.additional_info
            chunk_data.append(chunk)
        for i in range(0, tree.chunk_size()):
            c = tree.chunk(i)
            if c.link != -1:
                chunk_data[c.link].src_idx.append(i)
        return chunk_data

    def senti_analysis(self, sentence):
        """
        output: sentiment score (1:positive < score < -1:negative)
        """
        score = 0
        num_all_words = 0
        tokens = self.tokenize(sentence)
        words = list()
        words.extend([s.base_form.lower() for s in tokens])
        politely_dict = self.search_politely_dict(words)

        #print(politely_dict)
        scores = list()
        scores.extend([politely_dict[w] for w in words])
        for i in range(0, len(tokens)): # apply rules
            s = tokens[i]
            scores = self.apply_politely_reverse_rule_for_senti_analisys(i, tokens, scores, sentence)
        # evaluate score

        for sc in scores:
            score += sc
            num_all_words += 1
        return round(score/num_all_words, 2)

    def get_sentences(self, text):
        """
        input: text have many sentences
        output: ary of sentences ['sent1', 'sent2', ...]
        """
        EOS_DIC = ['。', '．', '！','？','!?', '!', '?' ]
        sentences = list()
        sent = ''
        for token in self.tokenize(text):
            # print(token.pos_jp, token.pos, token.surface, sent)
            # TODO: this is simple way. ex)「今日は雨ね。」と母がいった
            sent += token.surface
            if token.surface in EOS_DIC and sent != '':
                sentences.append(sent)
                sent = ''
        return sentences


    def tokenize(self, sent):
        node = self._tagger.parseToNode(sent)
        tokens = list()
        idx = 0
        while node:
            feature = node.feature.split(',')
            token = namedtuple('Token', 'idx, surface, pos, pos_detail1, pos_detail2, pos_detail3,\
                          infl_type, infl_form, base_form, reading, phonetic')
            token.idx         = idx
            token.surface     = node.surface  # 表層形
            token.pos_jp      = feature[0]    # 品詞
            token.pos_detail1 = feature[1]    # 品詞細分類1
            token.pos_detail2 = feature[2]    # 品詞細分類2
            token.pos_detail3 = feature[3]    # 品詞細分類3
            token.infl_type   = feature[4]    # 活用型
            token.infl_form   = feature[5]    # 活用形
            token.base_form   = feature[6]    # 原型
            token.pos         = self.POS_DIC.get( feature[0], 'X' )     # 品詞
            token.reading     = feature[7] if len(feature) > 7 else ''  # 読み
            token.phonetic    = feature[8] if len(feature) > 8 else ''  # 発音
            #
            tokens.append(token)
            idx += 1
            node = node.next
        return tokens

if __name__ == "__main__":
    jp = JpParser(sys_dic_path='C:\Program Files (x86)\MeCab\dic\ipadic')
    ignore_words = ["ゾンビランドサガ"]
    LEN = 20
    file= "../zombie_2018-11-30.json"
    import json
    result_file = file + ".senti"
    result_set = []

    with open(file, encoding="utf-8") as f:
        try:
            lines = f.readlines()
            p = 0
            n = 0
            e = 0
            i = 0
            for line in lines:
                tweet = json.loads(line)
                text = tweet["text"]
                if i % 500 == 0:
                    print(i)
                if len(text.replace(ignore_words[0], "")) < LEN:
                    continue
                score = jp.senti_analysis(text)

                result = {
                    "text": text,
                    "score": score,
                    "created_at": tweet["created_at"]
                }
                result_set.append(result)
                if score > 0:
                    p = +1
                elif score < 0:
                    n = +1
                else:
                    e = +1
                i += 1
        except:
            import traceback
            print(traceback.print_exc())
    f = open(result_file, "a", encoding="utf-8")
    for r in result_set:
        json.dump(r, f, ensure_ascii=False)
        f.write('\n')