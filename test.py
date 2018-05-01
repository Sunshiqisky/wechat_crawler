
# -*- coding: utf-8 -*-


import pandas as pd

display_columns = ["p_date","u_date","title","read_num","like_num","comment_num","reward_num"]


from pymongo import MongoClient
# 连接 mongodb
c = MongoClient()
print(c)
cursor = c.test['post'].find()
df = pd.DataFrame(list(cursor))

# 删除 "_id"列
df = df.drop("_id", axis=1)
# 重新设置列的顺序
df = df.reindex(columns=display_columns)
# 将p_date的数据类型从timestamp 转换成 datetime
df.p_date = pd.to_datetime(df['p_date'])
print(df)
df.to_csv('comments.csv')
