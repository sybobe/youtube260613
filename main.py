import re
import os
from collections import Counter

import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


st.set_page_config(
    page_title="유튜브 댓글 심층 분석기",
    page_icon="💬",
    layout="wide"
)

st.title("💬 유튜브 댓글 심층 분석기")
st.write("유튜브 링크를 입력하면 댓글을 수집하고, 반응·감성·핵심 키워드·한글 워드클라우드를 분석합니다.")


def get_api_key():
    try:
        return st.secrets["YOUTUBE_API_KEY"]
    except Exception:
        return None


def extract_video_id(url):
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"shorts/([a-zA-Z0-9_-]{11})",
        r"embed/([a-zA-Z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", url):
        return url

    return None


def clean_text(text):
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s!?ㅋㅋㅎㅠㅜ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize_korean_simple(text):
    stopwords = {
        "그리고", "그래서", "하지만", "진짜", "너무", "정말", "완전", "그냥",
        "이거", "저거", "영상", "댓글", "유튜브", "오늘", "이번", "저는", "제가",
        "입니다", "합니다", "ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "ㅜㅜ", "the", "and", "you",
        "for", "that", "this", "with", "have", "are", "was", "but"
    }

    words = re.findall(r"[가-힣a-zA-Z]{2,}", text.lower())
    words = [w for w in words if w not in stopwords and len(w) >= 2]
    return words


def simple_sentiment(text):
    positive_words = [
        "좋다", "좋아요", "최고", "대박", "멋지", "감사", "재밌", "웃기", "행복",
        "추천", "공감", "훌륭", "완벽", "사랑", "응원", "감동", "유익", "예쁘",
        "good", "great", "best", "love", "nice", "amazing", "awesome"
    ]

    negative_words = [
        "싫다", "별로", "최악", "실망", "화남", "짜증", "문제", "불편", "싫어",
        "노잼", "비추", "논란", "거짓", "불쾌", "나쁘", "망했", "억지",
        "bad", "hate", "worst", "angry", "problem", "boring"
    ]

    score = 0

    for word in positive_words:
        if word in text:
            score += 1

    for word in negative_words:
        if word in text:
            score -= 1

    if score > 0:
        return "긍정"
    elif score < 0:
        return "부정"
    else:
        return "중립"


@st.cache_data(show_spinner=False)
def fetch_comments(api_key, video_id, max_comments):
    youtube = build("youtube", "v3", developerKey=api_key)

    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(100, max_comments - len(comments)),
            pageToken=next_page_token,
            textFormat="plainText",
            order="relevance"
        )

        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "작성자": snippet.get("authorDisplayName", ""),
                "댓글": snippet.get("textDisplay", ""),
                "좋아요 수": snippet.get("likeCount", 0),
                "작성일": snippet.get("publishedAt", ""),
                "수정일": snippet.get("updatedAt", "")
            })

        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

    return pd.DataFrame(comments)


def make_wordcloud(text):
    font_candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    ]

    font_path = None
    for path in font_candidates:
        if os.path.exists(path):
            font_path = path
            break

    wc = WordCloud(
        font_path=font_path,
        width=1200,
        height=700,
        background_color="white",
        collocations=False,
        max_words=120
    ).generate(text)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    return fig


with st.sidebar:
    st.header("⚙️ 분석 설정")

    secret_key = get_api_key()

    if secret_key:
        api_key = secret_key
        st.success("Secrets에서 API 키를 불러왔습니다.")
    else:
        api_key = st.text_input(
            "YouTube API Key",
            type="password",
            help="Streamlit Cloud에서는 Secrets에 YOUTUBE_API_KEY로 저장하는 것을 추천합니다."
        )

    max_comments = st.slider(
        "수집할 댓글 수",
        min_value=50,
        max_value=1000,
        value=300,
        step=50
    )

    st.caption("댓글 수가 많을수록 분석은 풍부하지만 API 사용량과 로딩 시간이 늘어납니다.")


youtube_url = st.text_input(
    "🔗 유튜브 영상 링크를 입력하세요",
    placeholder="예: https://www.youtube.com/watch?v=XXXXXXXXXXX"
)

analyze_button = st.button("🚀 댓글 분석 시작", use_container_width=True)

if analyze_button:
    if not api_key:
        st.error("YouTube API 키를 입력하거나 Streamlit Secrets에 등록해주세요.")

    elif not youtube_url:
        st.warning("유튜브 링크를 입력해주세요.")

    else:
        video_id = extract_video_id(youtube_url)

        if not video_id:
            st.error("올바른 유튜브 링크 또는 영상 ID를 입력해주세요.")

        else:
            try:
                with st.spinner("댓글을 수집하고 분석하는 중입니다..."):
                    df = fetch_comments(api_key, video_id, max_comments)

                if df.empty:
                    st.warning("댓글을 불러오지 못했습니다. 댓글이 꺼져 있거나 공개 댓글이 없을 수 있습니다.")

                else:
                    df["정제 댓글"] = df["댓글"].apply(clean_text)
                    df["글자 수"] = df["정제 댓글"].str.len()
                    df["감성"] = df["정제 댓글"].apply(simple_sentiment)
                    df["질문 여부"] = df["댓글"].str.contains(r"\?", regex=True)
                    df["웃음 반응"] = df["댓글"].str.contains("ㅋ|ㅎ|😂|🤣", regex=True)
                    df["슬픔/공감 반응"] = df["댓글"].str.contains("ㅠ|ㅜ|😭", regex=True)

                    all_text = " ".join(df["정제 댓글"].dropna())
                    words = tokenize_korean_simple(all_text)
                    word_counts = Counter(words)

                    total_comments = len(df)
                    avg_length = df["글자 수"].mean()
                    total_likes = df["좋아요 수"].sum()
                    top_like_comment = df.sort_values("좋아요 수", ascending=False).iloc[0]

                    st.success(f"총 {total_comments}개의 댓글을 분석했습니다!")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("💬 분석 댓글 수", f"{total_comments:,}개")

                    with col2:
                        st.metric("❤️ 댓글 좋아요 합계", f"{total_likes:,}개")

                    with col3:
                        st.metric("✍️ 평균 댓글 길이", f"{avg_length:.1f}자")

                    with col4:
                        question_rate = df["질문 여부"].mean() * 100
                        st.metric("❓ 질문형 댓글 비율", f"{question_rate:.1f}%")

                    st.divider()

                    st.subheader("📊 댓글 감성 분석")

                    sentiment_count = df["감성"].value_counts().reset_index()
                    sentiment_count.columns = ["감성", "댓글 수"]

                    fig_sentiment = px.pie(
                        sentiment_count,
                        names="감성",
                        values="댓글 수",
                        title="댓글 감성 비율",
                        hole=0.45
                    )

                    st.plotly_chart(fig_sentiment, use_container_width=True)

                    st.divider()

                    st.subheader("☁️ 한글 워드클라우드")

                    if len(words) == 0:
                        st.warning("워드클라우드를 만들 수 있는 단어가 부족합니다.")
                    else:
                        wordcloud_text = " ".join(words)
                        fig_wc = make_wordcloud(wordcloud_text)
                        st.pyplot(fig_wc)

                    st.divider()

                    st.subheader("🔥 핵심 키워드 TOP 20")

                    top_words = pd.DataFrame(
                        word_counts.most_common(20),
                        columns=["키워드", "빈도"]
                    )

                    fig_words = px.bar(
                        top_words,
                        x="빈도",
                        y="키워드",
                        orientation="h",
                        title="댓글 핵심 키워드 순위",
                        text="빈도"
                    )

                    fig_words.update_layout(
                        yaxis=dict(categoryorder="total ascending"),
                        height=600
                    )

                    st.plotly_chart(fig_words, use_container_width=True)

                    st.divider()

                    st.subheader("❤️ 좋아요가 가장 많은 댓글")

                    st.info(
                        f"""
                        **작성자:** {top_like_comment['작성자']}

                        **좋아요 수:** {top_like_comment['좋아요 수']}

                        **댓글:**  
                        {top_like_comment['댓글']}
                        """
                    )

                    st.divider()

                    st.subheader("🧠 심층 해석")

                    positive_ratio = (df["감성"] == "긍정").mean() * 100
                    negative_ratio = (df["감성"] == "부정").mean() * 100
                    neutral_ratio = (df["감성"] == "중립").mean() * 100
                    laugh_ratio = df["웃음 반응"].mean() * 100
                    sad_ratio = df["슬픔/공감 반응"].mean() * 100

                    st.write(f"""
                    이 영상의 댓글 분위기는 **긍정 {positive_ratio:.1f}%**, 
                    **중립 {neutral_ratio:.1f}%**, **부정 {negative_ratio:.1f}%**로 나타났습니다.

                    웃음 또는 재미 반응은 **{laugh_ratio:.1f}%**, 
                    슬픔이나 공감 반응은 **{sad_ratio:.1f}%** 수준입니다.

                    핵심 키워드 상위 단어는 댓글 이용자들이 영상에서 가장 많이 반응한 주제입니다.  
                    워드클라우드에서 크게 보이는 단어일수록 시청자들이 반복적으로 언급한 관심 포인트라고 볼 수 있습니다.
                    """)

                    if positive_ratio > negative_ratio * 2:
                        st.success("전체적으로 호감도와 긍정 반응이 강한 영상입니다. 👍")
                    elif negative_ratio > positive_ratio:
                        st.error("부정 반응이 상대적으로 강합니다. 논란, 불만, 의견 충돌 가능성을 확인해볼 필요가 있습니다.")
                    else:
                        st.warning("긍정과 부정이 섞여 있습니다. 댓글의 세부 맥락을 함께 확인하는 것이 좋습니다.")

                    st.divider()

                    st.subheader("📋 원본 댓글 데이터")

                    st.dataframe(
                        df[["작성자", "댓글", "좋아요 수", "감성", "작성일"]],
                        use_container_width=True
                    )

                    csv = df.to_csv(index=False).encode("utf-8-sig")

                    st.download_button(
                        label="📥 분석 결과 CSV 다운로드",
                        data=csv,
                        file_name="youtube_comment_analysis.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

            except HttpError as e:
                st.error("YouTube API 오류가 발생했습니다.")
                st.code(str(e))
                st.write("""
                확인할 점:
                1. API 키가 올바른지 확인
                2. YouTube Data API v3가 활성화되어 있는지 확인
                3. 댓글이 비활성화된 영상인지 확인
                4. API 할당량을 초과했는지 확인
                """)

            except Exception as e:
                st.error("예상치 못한 오류가 발생했습니다.")
                st.code(str(e))

else:
    st.info("왼쪽에서 API 키를 입력하고, 유튜브 링크를 넣은 뒤 분석을 시작하세요.")

st.caption("※ 이 앱은 YouTube Data API v3를 활용합니다. 분석 결과는 참고용이며, 감성 분석은 간단한 규칙 기반 방식입니다.")
