# -*- coding: utf-8 -*-

import json
import logging
import time
from datetime import datetime
import urllib3
import requests

import utils
from models import Post

requests.packages.urllib3.disable_warnings()
from urllib.parse import urlsplit
import html

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] [%(levelname)s] : %(message)s')

logger = logging.getLogger(__name__)


class WeiXinCrawler:
    def crawl(self, offset=0):
        """
        爬取更多文章
        """

        # 后续需要根据加载更多文章的url，刷新appmsg_token和pass_ticket
        url = "https://mp.weixin.qq.com/mp/profile_ext?" \
              "action=getmsg&" \
              "__biz=MzUzNTcwNDkxNA==&" \
              "f=json&" \
              "offset={offset}&" \
              "count=10&is_ok=1&scene=124&uin=777&key=777&" \
              "pass_ticket=mxvGMDk3GtQtB%2Fz7%2FamxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf%2BxoQE91&" \
              "wxtoken=&" \
              "appmsg_token=954_nx0hbhWF1KtiNq5UU0KRCSg5ZRHxsOCj-1s5ig~~&x5=1&" \
              "f=json".format(offset=offset)

        # 从 Fiddler 获取最新的请求头参数
        headers = """
            Host: mp.weixin.qq.com
            Connection: keep-alive
            X-Requested-With: XMLHttpRequest
            User-Agent: Mozilla/5.0 (Linux; Android 4.4.2; GT-I9508 Build/KOT49H; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/57.0.2987.132 MQQBrowser/6.2 TBS/044028 Mobile Safari/537.36 MicroMessenger/6.5.23.1180 NetType/WIFI Language/zh_CN
            Accept: */*
            Referer: https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=MzUzNTcwNDkxNA==&scene=124&devicetype=android-19&version=26051732&lang=zh_CN&nettype=WIFI&a8scene=3&pass_ticket=mxvGMDk3GtQtB%2Fz7%2FamxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf%2BxoQE91&wx_header=1
            Accept-Encoding: gzip, deflate
            Accept-Language: zh-CN,en-US;q=0.8
            Cookie: rewardsn=; wxtokenkey=777; wxuin=2077110005; devicetype=android-19; version=26051732; lang=zh_CN; pass_ticket=mxvGMDk3GtQtB/z7/amxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf+xoQE91; wap_sid2=CPXduN4HElxqMnJ1ZnA4U3ZJN2c0cTBGZ3dxUmtUeHpYcm5nVUZYQzBKX0xOMm9qRmJzM2NIYllwa1NsaWQ1SmRlODlyLTRpUHNrcHM2eFNtbmcwUXJpNFZ6QUZBYm9EQUFBfjC585zXBTgNQJVO
            Q-UA2: QV=3&PL=ADR&PR=WX&PP=com.tencent.mm&PPVN=6.5.23&TBSVC=43602&CO=BK&COVC=044028&PB=GE&VE=GA&DE=PHONE&CHID=0&LCID=9422&MO= GT-I9508 &RL=1080*1920&OS=4.4.2&API=19
            Q-GUID: dfbda8a63deb21e36f9d6f1113b788cb
            Q-Auth: 31045b957cf33acf31e40be2f3e71c5217597676a9729f1b
            """

        headers = utils.headers_to_dict(headers)
        response = requests.get(url, headers=headers, verify=False)
        result = response.json()  #response为json格式
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

    @staticmethod
    def save(msg_list):
        msg_list = msg_list.replace("\/", "/") #去掉url中/的转义
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
        sub_data = utils.sub_dict(item, keys) #获取指定字段的信息
        post = Post(**sub_data)
        p_date = datetime.fromtimestamp(p_date)
        post["p_date"] = p_date
        logger.info('save data %s ' % post.title)
        try:
            post.save()
        except Exception as e:
            logger.error("保存失败 data=%s" % post.to_json(), exc_info=True)

    @staticmethod
    def update_post(post):
        """
        post 参数是从mongodb读取出来的一条数据
        稍后就是对这个对象进行更新保存
        :param post:
        :return:
        """

        data_url = "https://mp.weixin.qq.com/mp/getappmsgext?" \
                   "f=json&uin=777&" \
                   "key=777&" \
                   "pass_ticket=mxvGMDk3GtQtB%25252Fz7%25252FamxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf%25252BxoQE91&" \
                   "wxtoken=777&" \
                   "devicetype=android-19&" \
                   "cientversion=26051732&" \
                   "appmsg_token=954_MOJLemLCd3Gz0Aal3PPp0Qmza2kN9ibwtA0IyosHLQlOgxiRlgtrWkHFwC4lgSeOA0FmtshLamC-6ysv&x5=1&" \
                   "f=json"   #后续需要加载文章的url，刷新appmsg_token和pass_ticket
        # url转义处理
        content_url = html.unescape(post.content_url)
        # 截取content_url的查询参数部分
        content_url_params = urlsplit(content_url).query
        # 将参数转化为字典类型
        content_url_params = utils.str_to_dict(content_url_params, "&", "=")
        body = 'r=0.9146884263687687&__biz=MzUzNTcwNDkxNA%3D%3D&appmsg_type=9&mid=2247484203&sn=a0dbce888297a156a4e9c0542094e286&idx=1&scene=38&title=%25E5%25A4%259A%25E5%25B0%2591%25E4%25BA%25BA%25E5%259B%25A0%25E4%25B8%25BA%25E7%2594%25B5%25E5%25BD%25B1%25E5%258E%25BB%25E4%25BA%2586%25E8%25A5%25BF%25E8%2597%258F&ct=1524824855&abtest_cookie=BAABAAoACwAMAA0ABwA8ix4Ad4seAPKMHgBkjR4Af40eACaOHgAxjh4AAAA%3D&devicetype=android-19&version=%2Fmmbizwap%2Fzh_CN%2Fhtmledition%2Fjs%2Fappmsg%2Findex3d6703.js&is_need_ticket=0&is_need_ad=1&comment_id=0&is_need_reward=0&both_ad=0&reward_uin_count=0&send_time=&msg_daily_idx=1&is_original=0&is_only_read=1&req_id=0100A6NrRHtU5GqTevtLXpPn&pass_ticket=mxvGMDk3GtQtB%25252Fz7%25252FamxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf%25252BxoQE91&is_temp_url=0&item_show_type=undefined'
        data = utils.str_to_dict(body, "&", "=")
        data.update(content_url_params) #将content_url中的参数更新到body参数中

        # 通过Fiddler 获取 最新的值
        headers = """
Host: mp.weixin.qq.com
Connection: keep-alive
Content-Length: 796      
Origin: https://mp.weixin.qq.com
X-Requested-With: XMLHttpRequest
User-Agent: Mozilla/5.0 (Linux; Android 4.4.2; GT-I9508 Build/KOT49H; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/57.0.2987.132 MQQBrowser/6.2 TBS/044028 Mobile Safari/537.36 MicroMessenger/6.5.23.1180 NetType/WIFI Language/zh_CN
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Accept: */*
Referer: https://mp.weixin.qq.com/s?__biz=MzUzNTcwNDkxNA==&mid=2247484203&idx=1&sn=a0dbce888297a156a4e9c0542094e286&chksm=fa802716cdf7ae001b3e2b539fc790b997bee12233d1f5a6cb5add4b6a9df979fd586d6b7191&scene=38&ascene=0&devicetype=android-19&version=26051732&nettype=WIFI&abtest_cookie=BAABAAoACwAMAA0ABwA8ix4Ad4seAPKMHgBkjR4Af40eACaOHgAxjh4AAAA%3D&lang=zh_CN&pass_ticket=mxvGMDk3GtQtB%2Fz7%2FamxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf%2BxoQE91&wx_header=1
Accept-Encoding: gzip, deflate
Accept-Language: zh-CN,en-US;q=0.8
Cookie: rewardsn=; wxtokenkey=777; wxuin=2077110005; devicetype=android-19; version=26051732; lang=zh_CN; pass_ticket=mxvGMDk3GtQtB/z7/amxY8wfvoTGUfjVEBxYjf4M2oAEyk15qbbpyu6tf+xoQE91; wap_sid2=CPXduN4HElxKRHdkalRfS3hya3FLamVMa0FzMFNCeFR5eV95d0ZQZzdZQUw4TjFYMHY4RVFiQWtaRVN5TlAwTEEtTkNWd3NURnJ1V2VCUTRXemdSMjdXZzN5Z3E2Ym9EQUFBfjDhgZ3XBTgNQAE=
Q-UA2: QV=3&PL=ADR&PR=WX&PP=com.tencent.mm&PPVN=6.5.23&TBSVC=43602&CO=BK&COVC=044028&PB=GE&VE=GA&DE=PHONE&CHID=0&LCID=9422&MO= GT-I9508 &RL=1080*1920&OS=4.4.2&API=19
Q-GUID: dfbda8a63deb21e36f9d6f1113b788cb
Q-Auth: 31045b957cf33acf31e40be2f3e71c5217597676a9729f1b

        """

        headers = utils.headers_to_dict(headers)

        r = requests.post(data_url, data=data, verify=False, params=data_url_params, headers=headers)

        result = r.json()
        if result.get("appmsgstat"):
            post['read_num'] = result.get("appmsgstat").get("read_num")
            post['like_num'] = result.get("appmsgstat").get("like_num")
            post['reward_num'] = result.get("reward_total_count") #只有文章有赞赏的时候才会有此字段
            post['u_date'] = datetime.now()
            logger.info("「%s」read_num: %s like_num: %s reward_num: %s" %
                        (post.title, post['read_num'], post['like_num'], post['reward_num']))
            post.save()
        else:
            logger.warning(u"没有获取的真实数据，请检查请求参数是否正确，返回的数据为：data=%s" % r.text)
            exit()


if __name__ == '__main__':
    # 运行代码时请替换自己所抓公众号信息的url和header
    crawler = WeiXinCrawler()
    crawler.crawl()

    for post in Post.objects(reward_num=0):
        crawler.update_post(post)
        time.sleep(5) #sleep时间稍微久点，防止出现301错误
