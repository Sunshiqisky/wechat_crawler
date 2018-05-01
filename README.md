

# 微信公众号爬虫方案分析（爬取文艺相处公众号）

之前考虑过使用搜狗微信来爬取微信公众号信息，不过搜狗提供的数据有诸多弊端，比如文章链接是临时的，文章没有阅读量等指标，所以考虑通过手机客户端利用 Python 爬微信公众号文章。

因为微信公众平台并没有对外提供 Web 端入口，只能通过手机客户端查看公众号文章，所以使用Fiddler来进行抓包，分析微信公众号相关操作的请求信息，后面通过Python 代码来模拟微信请求。

# 抓取公众号所有历史文章

使用 Fiddler 抓包方式，打开手机某个微信公众号历史文章列表，上拉加载更多，此时可以找到加载更多文章的 URL 请求地址：

![加载更多](https://github.com/Sunshiqisky/wechat_crawler/blob/master/%E5%9B%BE%E7%89%87/%E8%8E%B7%E5%8F%96%E6%9B%B4%E5%A4%9A%E9%A1%B5%E9%9D%A2.png?raw=true)

分析response，几个字段信息：

> - ret：请求是否成功，0就表示成功
> - msg_count： 返回的数据条数
> - can_msg_continue： 是否还有下一页数据
> - next_offset： 下一次请求的起始位置
> - general_msg_list：真实数据

`general_msg_list`是历史文章里面的基本信息，包括每篇文章的标题、发布时间、摘要、链接地址、封面图等，而像文章的阅读数、点赞数、评论数、赞赏数这些数据都需要通过额外接口获取。

通过字段 `can_msg_continue` 确定是否继续抓取，再结合 `next_offset` 就可以加载更多数据，我们需要把 url 中可变的参数 `offset` 用变量来代替，递归调用直到 `can_msg_continue` 为 0 说明所有文章都爬取完了。

```
class WeiXinCrawler:
    def crawl(self, offset=0):
        """
        爬取更多文章
        """
        # appmsg_token需刷新
        url = "https://mp.weixin.qq.com/mp/profile_ext?" \
              "action=getmsg&" \
              "__biz=MzUzNTcwNDkxNA==&" \
              "f=json&offset={offset}&" \
              "count=10&is_ok=1&scene=124&uin=777&key=777&" \               	"pass_ticket=z%2FYMNxHa1GuVS1pHj99nPCf1uwQrkEaSJeztTLDcQCGGJx%2BH5evDSY9ooI3nDLQx&" \
              "wxtoken=&" \
              "appmsg_token=954_X70f2Zp%252BnwCvfxt6YdRWgETK3fRaWtXY80tJfQ~~&x5=1&" \
              "f=json".format(offset=offset)


        # 从 Fiddler 获取最新的请求头参数
        headers = """
        省略
        """
        # 将"Host: mp.weixin.qq.com"格式的字符串转换成字典类型转换成字典类型
        headers = utils.headers_to_dict(headers)
        response = requests.get(url, headers=headers, verify=False)
        result = response.json()
        if result.get("ret") == 0:
            msg_list = result.get("general_msg_list")
            logger.info("抓取数据：offset=%s, data=%s" % (offset, msg_list))
            self.save(msg_list)
            # 递归调用直到 can_msg_continue 为 0 说明所有文章都爬取完了
            has_next = result.get("can_msg_continue")
            if has_next == 1:
                next_offset = result.get("next_offset") #下一次请求的起始位置
                time.sleep(2)
                self.crawl(next_offset)
        else:
            # 错误消息
            logger.error("请求参数失效，请重新设置")
            exit()
```

# 将爬取的文章存储到`MongoDB`

关于数据的存储有很多选择，最简单的方式就是直接保存到 csv 文件中，这种方式操作简单，适合数据量少的情况，Python的标准库 csv 模块就可以直接支持。如果遇到数据量非常大的情况，就必须要用到专业的数据库系统，既可以使用 `MySQL` 这样的关系型数据库，也可以使用 `MongoDB` 一类的文档型数据库。用Python 操作 `MongoDB` 非常方便，无需定义表结构就可以直接将数据插入，所以使用`MongoDB` 来存储数据。

- 连接数据库

  ```
  # 连接 mongodb
  connect('ssq_weixin', host='localhost', port=27017)
  ```


- 定义数据模型

  ```
  class Post(Document):
      """
      文章信息
      """
      title = StringField()  # 文章标题
      content_url = StringField()  # 文章链接
      content = StringField()  # 文章内容
      digest = StringField()  # 文章摘要
      cover = URLField(validation=None)  # 封面图
      p_date = DateTimeField()  # 推送时间
      read_num = IntField(default=0)  # 阅读数
      like_num = IntField(default=0)  # 点赞数
      comment_num = IntField(default=0)  # 评论数
      reward_num = IntField(default=0)  # 赞赏数
      author = StringField()  # 作者
      u_date = DateTimeField(default=datetime.now)  # 最后更新时间
  ```


- 获取文章标题、文章链接等信息存入数据库

  ```
      @staticmethod
      def save(msg_list):

          msg_list = msg_list.replace("\/", "/")
          data = json.loads(msg_list)
          msg_list = data.get("list")
          for msg in msg_list:
              p_date = msg.get("comm_msg_info").get("datetime")
              msg_info = msg.get("app_msg_ext_info")  # 非图文消息没有此字段
              if msg_info:
                  WeiXinCrawler._insert(msg_info, p_date)
                  multi_msg_info = msg_info.get("multi_app_msg_item_list")
                  for msg_item in multi_msg_info:
                      WeiXinCrawler._insert(msg_item, p_date)
              else:
                  logger.warning(u"此消息不是图文推送，data=%s" % json.dumps(msg.get("comm_msg_info")))

      @staticmethod
      def _insert(item, p_date):
          keys = ('title', 'author', 'content_url', 'digest', 'cover', 'source_url')
          sub_data = utils.sub_dict(item, keys)
          post = Post(**sub_data)
          p_date = datetime.fromtimestamp(p_date)
          post["p_date"] = p_date
          logger.info('save data %s ' % post.title)
          try:
              post.save()
          except Exception as e:
              logger.error("保存失败 data=%s" % post.to_json(), exc_info=True)
  ```

  ​

# 获取阅读数、点赞数、赞赏数

点开一篇文章，通过 Fiddler 抓包分析，观察发现获取文章阅读数、点赞数的URL接口为：https://mp.weixin.qq.com/mp/getappmsgext ，后面有很多查询参数，请求方法为 POST。

![获取点赞数](https://github.com/Sunshiqisky/wechat_crawler/blob/master/%E5%9B%BE%E7%89%87/%E8%8E%B7%E5%8F%96%E7%82%B9%E8%B5%9E%E6%95%B0.png?raw=true)

取之前存取的 `content_url` 中的参数和获取点赞数的接口的`body`参数中，除了 `chksm` 其它几个参数都在，我们把 `content_url` 中的参数替换到body中 再来验证请求会不会正常返回数据。经过多次实验是ok的。

```
# 这个参数是从Fiddler中拷贝出 URL，然后提取出查询参数部分再转换成字典对象
# 稍后会作为参数传给request.post方法
data_url_params = {
将url中的查询参数转换为字典格式
}
body = '自己的请求体'
data = utils.str_to_dict(body, "&", "=") #将body的字符串转换为字典格式
data.update(content_url_params)

data_url = "https://mp.weixin.qq.com/mp/getappmsgext"

r = requests.post(data_url, data=data, verify=False, params=data_url_params, headers=headers)
```

开工：

```
if __name__ == '__main__':
    crawler = WeiXinCrawler()
    crawler.crawl()

    for post in Post.objects(reward_num=0):
        crawler.update_post(post)
        time.sleep(5) #sleep时间稍微久点，防止出现301错误
```

可以愉快的爬取啦！

![日志](https://github.com/Sunshiqisky/wechat_crawler/blob/master/%E5%9B%BE%E7%89%87/%E8%BF%90%E8%A1%8C%E6%97%A5%E5%BF%97.png?raw=true)



# 数据分析、可视化

后续可以利用Pandas对爬取的数据进行数据，通过Matplotlib 对数据进行可视化展示。时间有限暂时先不做了。