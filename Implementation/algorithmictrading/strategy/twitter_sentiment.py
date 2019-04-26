import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from textblob import TextBlob
import re
from sklearn.neural_network import MLPClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn import linear_model
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn import svm
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
# from keras.models import Sequential
# from keras.layers import Dense
# from keras.layers import LSTM
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
import math
import graphviz
from sklearn import tree


from algorithmictrading.stockData.getTweets import tweetDataRetriever
from algorithmictrading.stockData.getStock import stockDataRetriever

''' twitter part of df is grouped by 3 -- 0 = sentiment, 1= favorite count,
2= retweet count '''
def execute(stock_name, start_date, end_date, fetchStocks):
    np.random.seed(1)
    if fetchStocks:  # build twitter sentiment and merge into stock data 
        df = build_df(stock_name, start_date, end_date)
    else:
        df = tweetDataRetriever(stock_name).fetch_merged_tweet()

    # create buy/sell signals using different techniques
    correlation(df, stock_name)
    naive_sentiment(df, stock_name)
    #machine_learning_sentiment(df, stock_name)
    #machine_learning_sentiment_boosted(df, stock_name)
    #deep_learning_sentiment(df, stock_name)


def build_df(stock_name, start_date, end_date):
    # get tweet sentiment
    print("getting tweet sentiment")
    data = tweetDataRetriever(stock_name).fetch_tweet()
    data["Date"] = ""
    sentiment = []
    for tweet in data["text"]:
        sentiment.append(tweet_sentiment(tweet))
    data["Sentiment"] = sentiment

    # convert twitter date format for merge with stock data 
    print("converting dates")
    date_conv = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', "May": '05', "Jun": '06', "Jul": '07', "Aug": '08', "Sep": '09', "Oct": '10', "Nov": '11', "Dec": '12'}
    for i, row in data.iterrows():
        raw = data["created_at"][i].split()
        #data["Date"][i] = raw[5] + "-" + date_conv[raw[1]] + "-" + raw[2] 
        data.loc[i, "Date"] = raw[5] + "-" + date_conv[raw[1]] + "-" + raw[2] 

    # drop tweet replies
    print("dropping replies")
    for i, row in data.iterrows():
        if isinstance(data["in_reply_to_screen_name"][i], str):
            #print(row, data["in_reply_to_screen_name"][row])
            data = data.drop(i)

    # aggregate tweets on same day 
    print("aggregating tweets")
    data = data.groupby("Date")[["Sentiment", "favorite_count", "retweet_count"]].apply(lambda x: x.values.tolist())
    data = data.to_frame('twitter').reset_index()

    # merge tweets with stock data 
    print("merging")
    data_stock = stockDataRetriever(stock_name, start_date, end_date).fetchStock(True)
    df = data_stock.merge(data, how="left", on='Date')

    # create average sentiment
    print("creating average sentiment, other important values")
    average_sentiment_other_values(df)

    # create indicators for supervised learning
    print("creating indicators for learning")
    df["change"] = df["Close"].diff()
    df["change"] = df["change"].fillna(0)
    df["change_int"] = 0
    for i, row in df.iterrows():
        val = -1
        if float(df["change"][i]) > 0:
            val = 1
        df.loc[i, "change_int"] = val

    df.to_csv("./twitterCSV/" + stock_name[5:] + "_MERGED.csv")
    return df

def correlation(df, stock_name):
    for row in df.itertuples():
        if len(str(df["twitter"][row.Index])) > 3:
            break
    first_tweet = row.Index 
    pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "total_tweets", "total_retweets", "total_favorites", "change", "change_int"]]

    scaler = MinMaxScaler()
    pre_df["avg_sentiment"] = scaler.fit_transform(pre_df["avg_sentiment"].reshape(-1, 1))
    pre_df["total_tweets"] = scaler.fit_transform(pre_df["total_tweets"].reshape(-1, 1))
    pre_df["total_retweets"] = scaler.fit_transform(pre_df["total_retweets"].reshape(-1, 1))
    pre_df["total_favorites"] = scaler.fit_transform(pre_df["total_favorites"].reshape(-1, 1))
    print("testing correlation of", stock_name)
    print("sentiment", np.corrcoef(pre_df["avg_sentiment"],pre_df["Close"])[0][1])
    print("favorites", np.corrcoef(pre_df["total_favorites"],pre_df["Close"])[0][1])
    print("retweets", np.corrcoef(pre_df["total_retweets"],pre_df["Close"])[0][1])
    print("total_tweets",np.corrcoef(pre_df["total_tweets"],pre_df["Close"])[0][1])
    print("")

def naive_sentiment(df, stock_name):
    # find first tweet date
    for row in df.itertuples():
        if len(str(df["twitter"][row.Index])) > 3:
            break
    first_tweet = row.Index# use test size for comparable results
    pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "total_tweets", "total_retweets", "total_favorites", "change", "change_int"]]
    pre_df = pre_df.reset_index(drop=True)

    pre_df['change_predicted'] = 0
    for i, row in pre_df.iterrows():
        if pre_df["avg_sentiment"][i] > .25:
            pre_df["change_predicted"][i] = 1
        elif pre_df["avg_sentiment"][i] < 0:
            pre_df["change_predicted"][i] = -1

    profit(pre_df, stock_name, "naive strategy")


def machine_learning_sentiment(df, stock_name):  # model may see the trend for us!
    # SUPRESSES WARNINGS
    def warn(*args, **kwargs):
        pass
    import warnings
    warnings.warn = warn  
    # find first tweet date
    for row in df.itertuples():
        if len(str(df["twitter"][row.Index])) > 3:
            break
    first_tweet = row.Index 
    pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "total_tweets", "total_retweets", "total_favorites", "change", "change_int"]]
    #pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "change", "change_int"]]
    pre_df["change_predicted"] = 0

    scaler = MinMaxScaler()
    pre_df["avg_sentiment"] = scaler.fit_transform(pre_df["avg_sentiment"].reshape(-1, 1))
    pre_df["total_tweets"] = scaler.fit_transform(pre_df["total_tweets"].reshape(-1, 1))
    pre_df["total_retweets"] = scaler.fit_transform(pre_df["total_retweets"].reshape(-1, 1))
    pre_df["total_favorites"] = scaler.fit_transform(pre_df["total_favorites"].reshape(-1, 1))
    print("testing effectiveness of", stock_name)

    ## Regressor ##

    train = pre_df[:int(len(pre_df)*2/3)].drop(["change_int"], axis=1)
    test = pre_df[-int(len(pre_df)*1/3):].drop(["change", "change_int"], axis=1)
    X = train.drop(["change"],axis=1)
    y = train["change"]
    rf = RandomForestRegressor(n_estimators=100)
    rf.fit(X,y)
    print(type(rf), rf.score(X,y)) # gives r2
    test["change_predicted"] = rf.predict(test)
    test = test.reset_index(drop=True)

    profit(test, stock_name, type(rf))

    ## Classifiers ##

    train = pre_df[:int(len(pre_df)*2/3)].drop(["change"], axis=1)
    test = pre_df[-int(len(pre_df)*1/3):].drop(["change_int", "change"], axis=1)
    test_profit = test.copy(deep=True)
    X = train.drop(["change_int"], axis=1)
    y = train["change_int"]  # NEED TO USE INTS FOR THE NEURAL NETWORK STUFF

    clfs = [
        MLPClassifier(hidden_layer_sizes=(100, 100, 100), max_iter=500, alpha=0.0001, solver='sgd', verbose=10),
        DecisionTreeClassifier(),
        KNeighborsClassifier(n_neighbors=5)]

    for clf in clfs:
        clf.fit(X,y)
        print(type(clf), cross_val_score(clf, X, y, scoring='accuracy').mean())
        predicted_movement = clf.predict(test)
        test_profit["change_predicted"] = predicted_movement
        test_profit = test_profit.reset_index(drop=True)
        profit(test_profit, stock_name, type(clf))

        # visualizing decision tree
        # data = tree.export_graphviz(clf, out_file=None)
        # graph = graphviz.Source(data)
        # graph.render("decision tree")

def machine_learning_sentiment_boosted(df, stock_name):  # model may see the trend for us!
    # SUPRESSES WARNINGS
    def warn(*args, **kwargs):
        pass
    import warnings
    warnings.warn = warn  
    # find first tweet date
    for row in df.itertuples():
        if len(str(df["twitter"][row.Index])) > 3:
            break
    first_tweet = row.Index 
    #pre_df = df[first_tweet:].drop(["Date", "twitter", "Ex-Dividend", "Split Ratio"], axis=1) # get rid of strings
    #pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "total_tweets", "total_retweets", "total_favorites", "change", "change_int"]]
    pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "total_tweets", "total_retweets", "total_favorites", "change", "change_int"]]
    pre_df["change_predicted"] = 0

    scaler = MinMaxScaler()
    pre_df["avg_sentiment"] = scaler.fit_transform(pre_df["avg_sentiment"].reshape(-1, 1))
    pre_df["total_tweets"] = scaler.fit_transform(pre_df["total_tweets"].reshape(-1, 1))
    pre_df["total_retweets"] = scaler.fit_transform(pre_df["total_retweets"].reshape(-1, 1))
    pre_df["total_favorites"] = scaler.fit_transform(pre_df["total_favorites"].reshape(-1, 1))
    print("testing effectiveness of", stock_name)


    ## Regressor ##


    train = pre_df[:int(len(pre_df)*2/3)].drop(["change_int"], axis=1)
    test = pre_df[-int(len(pre_df)*1/3):].drop(["change", "change_int"], axis=1)
    test_profit = test.copy(deep=True)
    X = train.drop(["change"],axis=1)
    y = train["change"]
    rf = RandomForestRegressor(n_estimators=100)
    rf.fit(X,y)
    print(type(rf), rf.score(X,y)) # gives r2
    test_profit["rfreg"] = rf.predict(test)



    ## Classifiers ##

    train = pre_df[:int(len(pre_df)*2/3)].drop(["change"], axis=1)
    test = pre_df[-int(len(pre_df)*1/3):].drop(["change_int", "change"], axis=1)
    X = train.drop(["change_int"], axis=1)
    y = train["change_int"]  # NEED TO USE INTS FOR THE NEURAL NETWORK STUFF

    clfs = [
        MLPClassifier(hidden_layer_sizes=(100, 100, 100), max_iter=500, alpha=0.0001, solver='sgd', verbose=10),
        DecisionTreeClassifier(),
        KNeighborsClassifier(n_neighbors=5)]

    clf_arr = ['mlp', 'dtree', 'kneighbors']
    index = 0
    for clf in clfs:
        clf.fit(X,y)
        print(type(clf), cross_val_score(clf, X, y, scoring='accuracy').mean()) #THIS ONLYWORKS FOR CLASSIFIERS
        predicted_movement = clf.predict(test)

        test_profit[clf_arr[index]] = predicted_movement
        index += 1

    test_profit = test_profit.reset_index(drop=True)

    # conservative strategy - sell if any of models predicts a downtrend
    if np.count_nonzero(test_profit['mlp'].values == -1) == len(test_profit):  # sometimes mlp only predicts sell signals
        for i, row in test_profit.iterrows():
            if test_profit['rfreg'][i] < 0 or test_profit['dtree'][i] < 0 or test_profit['kneighbors'][i] < 0:
                test_profit["change_predicted"][i] = -1
            else:
                test_profit["change_predicted"][i] = 1
    else:
        for i, row in test_profit.iterrows():
            if test_profit['rfreg'][i] < 0 or test_profit['mlp'][i] < 0 or test_profit['dtree'][i] < 0 or test_profit['kneighbors'][i] < 0:
                test_profit["change_predicted"][i] = -1
            else:
                test_profit["change_predicted"][i] = 1

    profit(test_profit, stock_name, "<BOOSTING - Strategy conservative>")

    # leniant model - buy if more than half buy signals
    for i, row in test_profit.iterrows():
        if np.sign(test_profit['rfreg'][i]) + test_profit['mlp'][i] + test_profit['dtree'][i] + test_profit['kneighbors'][i] >= 2:
            test_profit["change_predicted"][i] = 1
        else:
            test_profit["change_predicted"][i] = -1

    profit(test_profit, stock_name, "<BOOSTING - Strategy leniant>")


def deep_learning_sentiment(df, stock_name):
    # Multiple input series LSTM
    for row in df.itertuples():
        if len(str(df["twitter"][row.Index])) > 3:
            break
    first_tweet = row.Index 
    pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment", "total_tweets", "total_retweets", "total_favorites"]]
    #pre_df = df.loc[first_tweet:, ["Close", "avg_sentiment"]]  # Close must be first in df!
    dataset = pre_df.values

    scaler = MinMaxScaler()
    dataset = scaler.fit_transform(dataset)

    data_train = dataset[0:int(len(dataset)*2/3), :]
    data_test = dataset[int(len(dataset)*2/3):len(dataset), :]

    look_back = 60

    x_train, y_train = [], []
    for i in range(look_back, len(data_train)):
        x_train.append(data_train[i-look_back:i])
        y_train.append(data_train[i, 0])
    x_train, y_train = np.array(x_train), np.array(y_train)

    x_test, y_test = [], []
    for i in range(look_back, len(data_test)):
        x_test.append(data_test[i-look_back:i])
        y_test.append(data_test[i, 0])
    x_test, y_test = np.array(x_test), np.array(y_test)

    model = Sequential() # input shape - first is the time period used, second is amount of inputed columns (features)
    model.add(LSTM(units=50, return_sequences=True, input_shape=(look_back, x_train.shape[2])))
    model.add(LSTM(units=50))
    model.add(Dense(1))
    model.compile(loss='mean_squared_error', optimizer='adam')
    model.fit(x_train, y_train, epochs=100, batch_size=32, verbose=2)
    predict = model.predict(x_test, verbose=0)
    predicted = predict

    for i in range(len(pre_df.columns.values.tolist())-1):
        predicted = np.append(predicted, np.ones([len(predict), 1]), 1)

    predicted = scaler.inverse_transform(predicted)

    test_df = pre_df[int(len(dataset)*2/3) + look_back:]

    testScore = math.sqrt(mean_squared_error(test_df["Close"], predicted[:, 0]))
    print('Test Score of %s: %.2f RMSE' % (stock_name, testScore))

    test_df["predicted"] = predicted[:, 0]
    test_df = test_df.reset_index(drop=True)

    # strategy - if predicted price is less than current close, then sell, if above current close then buy
    for i, row in test_df.iterrows():
        if test_df["Close"].iloc[i] < test_df["predicted"].iloc[i]:
            change_predicted = 1
        else:
            change_predicted = -1
        test_df.loc[i, "change_predicted"] = change_predicted

    return profit(test_df, stock_name, type(model))


def average_sentiment_other_values(df):
    df["avg_sentiment"] = 0
    df["total_tweets"] = 0
    df["total_retweets"] = 0
    df["total_favorites"] = 0
    for row in df.itertuples():
        i = row.Index
        if len(str(df["twitter"][i])) > 3:  # ignore nan
            sent = str(df["twitter"][i]).split(',')
            trim = "[]"
            sentiment = []
            for s in sent:
                sentiment.append(float(''.join(i for i in s if i not in trim)))

            tot_sentiment = 0
            tot_rt = 0
            tot_fave = 0
            for sent,rt,fv in zip(*[iter(sentiment)]*3):
                tot_sentiment += sent
                tot_rt += rt
                tot_fave += fv

            avg_sentiment = float(tot_sentiment)/(len(sentiment)/3)

            df.loc[i, "avg_sentiment"] = avg_sentiment
            df.loc[i, "total_tweets"] = len(sentiment)/3
            df.loc[i, "total_retweets"] = tot_rt
            df.loc[i, "total_favorites"] = tot_fave


def clean_tweet(tweet):
    return ' '.join(re.sub("(@[A-Za-z0-9]+)|([^0-9A-Za-z \t])|(\w+:\/\/\S+)", " ", tweet).split())


def tweet_sentiment(tweet):
    blob = TextBlob(clean_tweet(tweet))
    return float(blob.sentiment.polarity)


def profit(df, name, clf_type):

    #df = df.dropna()

    bank = 1000
    base = 1000
    shares = 0

    baseline_shares = int(bank / df["Close"].iloc[0])
    baseline_value = bank - df["Close"].iloc[0]*baseline_shares

    #print(baseline_shares, baseline_value, baseline_shares * df["Close"].iloc[len(df) - 1])

    for i, row in df.iterrows():
        if df["change_predicted"][i] > 0:
            purchased = int(float(bank) / df["Close"].iloc[i])
            bank -= purchased * df["Close"].iloc[i]
            shares += purchased
        else:
            bank += float(df["Close"].iloc[i]) * shares
            shares = 0
        #print(bank, shares)
    bank += df["Close"].iloc[i] * shares

    baseline_value += baseline_shares * df["Close"].iloc[len(df) - 1]

    print(name, clf_type, "Total Money:", bank, "percent_return", (bank-base)/base * 100, "baseline:",
          baseline_value, "years of trading:", "{0:.2f}".format((len(df)-1)/float(252)))
