#!/usr/bin/env python
# coding: utf-8
import qrcode
import urllib, urllib2,datetime,uuid
import cookielib
import requests
import xml.dom.minidom
import json
import time, re, sys, os, random
import multiprocessing
import platform
import logging
from collections import defaultdict
from urlparse import urlparse
from lxml import html
from pymongo import MongoClient 


topics=None
users=None


def catchKeyboardInterrupt(fn):
	def wrapper(*args):
		try:
			return fn(*args)
		except KeyboardInterrupt:
			print '\n[*] 强制退出程序'
			logging.debug('[*] 强制退出程序')
	return wrapper

def _decode_list(data):
	rv = []
	for item in data:
		if isinstance(item, unicode):
			item = item.encode('utf-8')
		elif isinstance(item, list):
			item = _decode_list(item)
		elif isinstance(item, dict):
			item = _decode_dict(item)
		rv.append(item)
	return rv

def _decode_dict(data):
	rv = {}
	for key, value in data.iteritems():
		if isinstance(key, unicode):
			key = key.encode('utf-8')
		if isinstance(value, unicode):
			value = value.encode('utf-8')
		elif isinstance(value, list):
			value = _decode_list(value)
		elif isinstance(value, dict):
			value = _decode_dict(value)
		rv[key] = value
	return rv

class WebWeixin(object):
	def __str__(self):
		description = \
		"=========================\n" + \
		"[#] Web Weixin\n" + \
		"[#] Debug Mode: " + str(self.DEBUG) + "\n" + \
		"[#] Uuid: " + self.uuid + "\n" + \
		"[#] Uin: " + str(self.uin) + "\n" + \
		"[#] Sid: " + self.sid + "\n" + \
		"[#] Skey: " + self.skey + "\n" + \
		"[#] DeviceId: " + self.deviceId + "\n" + \
		"[#] PassTicket: " + self.pass_ticket + "\n" + \
		"========================="
		return description

	def __init__(self):
		self.DEBUG = False
		self.uuid = ''
		self.base_uri = ''
		self.redirect_uri= ''
		self.uin = ''
		self.sid = ''
		self.skey = ''
		self.pass_ticket = ''
		self.deviceId = 'e' + repr(random.random())[2:17]
		self.BaseRequest = {}
		self.synckey = ''
		self.SyncKey = []
		self.User = []
		self.MemberList = []
		self.ContactList = [] # 好友
		self.GroupList = []	# 群
		self.GroupMemeberList = [] # 群友
		self.PublicUsersList = [] # 公众号／服务号
		self.SpecialUsersList = [] # 特殊账号
		self.autoReplyMode = False
		self.syncHost = ''
		self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'
		self.interactive = False
		self.autoOpen = False
		self.saveFolder = os.path.join(os.getcwd(), 'saved')
		self.saveSubFolders = {'webwxgeticon': 'icons', 'webwxgetheadimg': 'headimgs', 'webwxgetmsgimg': 'msgimgs', 'webwxgetvideo': 'videos', 'webwxgetvoice': 'voices', '_showQRCodeImg': 'qrcodes'}
		self.appid = 'wx782c26e4c19acffb'
		self.lang = 'zh_CN'
		self.lastCheckTs = time.time()
		self.memberCount = 0
		self.SpecialUsers = ['newsapp', 'fmessage', 'filehelper', 'weibo', 'qqmail', 'fmessage', 'tmessage', 'qmessage', 'qqsync', 'floatbottle', 'lbsapp', 'shakeapp', 'medianote', 'qqfriend', 'readerapp', 'blogapp', 'facebookapp', 'masssendapp', 'meishiapp', 'feedsapp', 'voip', 'blogappweixin', 'weixin', 'brandsessionholder', 'weixinreminder', 'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'officialaccounts', 'notification_messages', 'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'wxitil', 'userexperience_alarm', 'notification_messages']
		self.TimeOut = 20 # 同步最短时间间隔（单位：秒）


		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
		opener.addheaders = [('User-agent', self.user_agent)]
		urllib2.install_opener(opener)

	def loadConfig(self, config):
		if config['DEBUG']: self.DEBUG = config['DEBUG']
		if config['autoReplyMode']: self.autoReplyMode = config['autoReplyMode']
		if config['user_agent']: self.user_agent = config['user_agent']
		if config['interactive']: self.interactive = config['interactive']
		if config['autoOpen']: self.autoOpen = config['autoOpen']

	def getUUID(self):
		url = 'https://login.weixin.qq.com/jslogin'
		params = {
			'appid': self.appid,
			'fun': 'new',
			'lang': self.lang,
			'_': int(time.time()),
		}
		data = self._post(url, params, False)
		regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
		pm = re.search(regx, data)
		if pm:
			code = pm.group(1)
			self.uuid = pm.group(2)
			return code == '200'
		return False

	def genQRCode(self):
		if sys.platform.startswith('win'):
			self._showQRCodeImg()
		else:
			self._str2qr('https://login.weixin.qq.com/l/' + self.uuid)

	def _showQRCodeImg(self):
		url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
		params = {
			't' : 'webwx',
			'_' : int(time.time())
		}

		data = self._post(url, params, False)
		QRCODE_PATH = self._saveFile('qrcode.jpg', data, '_showQRCodeImg')
		os.startfile(QRCODE_PATH)

	def waitForLogin(self, tip = 1):
		time.sleep(1)
		url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (tip, self.uuid, int(time.time()))
		data = self._get(url)
		pm = re.search(r'window.code=(\d+);', data)
		code = pm.group(1)

		if code == '201': return True
		elif code == '200':
			pm = re.search(r'window.redirect_uri="(\S+?)";', data)
			r_uri = pm.group(1) + '&fun=new'
			self.redirect_uri = r_uri
			self.base_uri = r_uri[:r_uri.rfind('/')]
			return True
		elif code == '408':
			self._echo('[登陆超时] \n')
		else:
			self._echo('[登陆异常] \n')
		return False

	def login(self):
		data = self._get(self.redirect_uri)
		doc = xml.dom.minidom.parseString(data)
		root = doc.documentElement

		for node in root.childNodes:
			if node.nodeName == 'skey':
				self.skey = node.childNodes[0].data
			elif node.nodeName == 'wxsid':
				self.sid = node.childNodes[0].data
			elif node.nodeName == 'wxuin':
				self.uin = node.childNodes[0].data
			elif node.nodeName == 'pass_ticket':
				self.pass_ticket = node.childNodes[0].data

		if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
			return False

		self.BaseRequest = {
			'Uin': int(self.uin),
			'Sid': self.sid,
			'Skey': self.skey,
			'DeviceID': self.deviceId,
		}
		return True

	def webwxinit(self):
		url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (self.pass_ticket, self.skey, int(time.time()))
		params = {
			'BaseRequest': self.BaseRequest
		}
		dic = self._post(url, params)
		self.SyncKey = dic['SyncKey']
		self.User = dic['User']
		# synckey for synccheck
		self.synckey = '|'.join([ str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List'] ])

		return dic['BaseResponse']['Ret'] == 0

	def webwxstatusnotify(self):
		url = self.base_uri + '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			"Code": 3,
			"FromUserName": self.User['UserName'],
			"ToUserName": self.User['UserName'],
			"ClientMsgId": int(time.time())
		}
		dic = self._post(url, params)

		return dic['BaseResponse']['Ret'] == 0

	def webwxgetcontact(self):
		SpecialUsers = self.SpecialUsers
		url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (self.pass_ticket, self.skey, int(time.time()))
		dic = self._post(url, {})

		self.MemberCount = dic['MemberCount']
		self.MemberList = dic['MemberList']
		ContactList = self.MemberList[:]
		GroupList = self.GroupList[:]
		PublicUsersList = self.PublicUsersList[:]
		SpecialUsersList = self.SpecialUsersList[:]

		for i in xrange(len(ContactList) - 1, -1, -1):
			Contact = ContactList[i]
			if Contact['VerifyFlag'] & 8 != 0: # 公众号/服务号
				ContactList.remove(Contact)
				self.PublicUsersList.append(Contact)
			elif Contact['UserName'] in SpecialUsers: # 特殊账号
				ContactList.remove(Contact)
				self.SpecialUsersList.append(Contact)
			elif Contact['UserName'].find('@@') != -1: # 群聊
				ContactList.remove(Contact)
				self.GroupList.append(Contact)
			elif Contact['UserName'] == self.User['UserName']: # 自己
				ContactList.remove(Contact)
		self.ContactList = ContactList

		return True

	def webwxbatchgetcontact(self):
		url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			"Count": len(self.GroupList),
			"List": [ {"UserName": g['UserName'], "EncryChatRoomId":""} for g in self.GroupList ]
		}
		dic = self._post(url, params)
		
		# blabla ...
		ContactList = dic['ContactList']
		ContactCount = dic['Count']
		self.GroupList = ContactList

		for i in xrange(len(ContactList) - 1, -1, -1):
			Contact = ContactList[i]
			MemberList = Contact['MemberList']
			for member in MemberList:
				self.GroupMemeberList.append(member)
		return True

	def getNameById(self, id):
		url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			"Count": 1,
			"List": [ {"UserName": id, "EncryChatRoomId":""} ]
		}
		dic = self._post(url, params)
		
		# blabla ...
		return dic['ContactList']

	def testsynccheck(self):
		SyncHost = [
			'webpush.weixin.qq.com',
			'webpush2.weixin.qq.com',
			'webpush.wechat.com',
			'webpush1.wechat.com',
			'webpush2.wechat.com',
			'webpush1.wechatapp.com',
			# 'webpush.wechatapp.com'
		]
		for host in SyncHost:
			self.syncHost = host
			[retcode, selector] = self.synccheck()
			if retcode == '0': return True
		return False

	def synccheck(self):
		params = {
			'r': int(time.time()),
			'sid': self.sid,
			'uin': self.uin,
			'skey': self.skey,
			'deviceid': self.deviceId,
			'synckey': self.synckey,
			'_': int(time.time()),
		}
		url = 'https://' + self.syncHost + '/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode(params)
		data = self._get(url)
		pm = re.search(r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}', data)
		retcode = pm.group(1)
		selector = pm.group(2)
		return [retcode, selector]

	def webwxsync(self):
		url = self.base_uri + '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (self.sid, self.skey, self.pass_ticket)
		params = {
			'BaseRequest': self.BaseRequest,
			'SyncKey': self.SyncKey,
			'rr': ~int(time.time())
		}
		dic = self._post(url, params)
		if self.DEBUG:
			print json.dumps(dic, indent=4)
			logging.debug(json.dumps(dic, indent=4))

		if dic['BaseResponse']['Ret'] == 0:
			self.SyncKey = dic['SyncKey']
			self.synckey = '|'.join([ str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List'] ])
		return dic

	def webwxsendmsg(self, word, to = 'filehelper'):
		url = self.base_uri + '/webwxsendmsg?pass_ticket=%s' % (self.pass_ticket)
		clientMsgId = str(int(time.time()*1000)) + str(random.random())[:5].replace('.','')
		params = {
			'BaseRequest': self.BaseRequest,
			'Msg': {
				"Type": 1,
				"Content": self._transcoding(word),
				"FromUserName": self.User['UserName'],
				"ToUserName": to,
				"LocalID": clientMsgId,
				"ClientMsgId": clientMsgId
			}
		}
		headers = {'content-type': 'application/json; charset=UTF-8'}
		data = json.dumps(params, ensure_ascii=False).encode('utf8')
		r = requests.post(url, data = data, headers = headers)
		dic = r.json()
		return dic['BaseResponse']['Ret'] == 0

	def _saveFile(self, filename, data, api=None):
		fn = filename
		if self.saveSubFolders[api]:
			dirName = os.path.join(self.saveFolder, self.saveSubFolders[api])
			if not os.path.exists(dirName):
				os.makedirs(dirName)
			fn = os.path.join(dirName, filename)
			logging.debug('Saved file: %s' % fn)
			with open(fn, 'wb') as f: f.write(data); f.close()
		return fn

	def webwxgeticon(self, id):
		url = self.base_uri + '/webwxgeticon?username=%s&skey=%s' % (id, self.skey)
		data = self._get(url)
		fn = 'img_'+id+'.jpg'
		return self._saveFile(fn, data, 'webwxgeticon')

	def webwxgetheadimg(self, id):
		url = self.base_uri + '/webwxgetheadimg?username=%s&skey=%s' % (id, self.skey)
		data = self._get(url)
		fn = 'img_'+id+'.jpg'
		return self._saveFile(fn, data, 'webwxgetheadimg')

	def webwxgetmsgimg(self, msgid):
		url = self.base_uri + '/webwxgetmsgimg?MsgID=%s&skey=%s' % (msgid, self.skey)
		data = self._get(url)
		fn = 'img_'+msgid+'.jpg'
		return self._saveFile(fn, data, 'webwxgetmsgimg')

	# Not work now for weixin haven't support this API
	def webwxgetvideo(self, msgid):
		url = self.base_uri + '/webwxgetvideo?msgid=%s&skey=%s' % (msgid, self.skey)
		data = self._get(url, api='webwxgetvideo')
		fn = 'video_'+msgid+'.mp4'
		return self._saveFile(fn, data, 'webwxgetvideo')

	def webwxgetvoice(self, msgid):
		url = self.base_uri + '/webwxgetvoice?msgid=%s&skey=%s' % (msgid, self.skey)
		data = self._get(url)
		fn = 'voice_'+msgid+'.mp3'
		return self._saveFile(fn, data, 'webwxgetvoice')

	def getGroupName(self, id):
		name = '未知群'
		for member in self.GroupList:
			if member['UserName'] == id:
				name = member['NickName']
		if name == '未知群':
			# 现有群里面查不到
			GroupList = self.getNameById(id)
			for group in GroupList:
				self.GroupList.append(group)
				if group['UserName'] == id:
					name = group['NickName']
					MemberList = group['MemberList']
					for member in MemberList:
						self.GroupMemeberList.append(member)
		return name

	def getUserById(self,id):
		for member in self.PublicUsersList:
			if member['UserName'] == id:
				return member
		return None
	def getUserRemarkName(self, id):
		name = '未知群' if id[:2] == '@@' else '陌生人'
		if id == self.User['UserName']: return self.User['NickName']	# 自己

		if id[:2] == '@@':
			# 群
			name = self.getGroupName(id)	
		else:
			# 特殊账号
			for member in self.SpecialUsersList:
				if member['UserName'] == id:
					name = member['RemarkName'] if member['RemarkName'] else member['NickName']

			# 公众号或服务号
			for member in self.PublicUsersList:
				if member['UserName'] == id:
					name = member['RemarkName'] if member['RemarkName'] else member['NickName']

			# 直接联系人
			for member in self.ContactList:
				if member['UserName'] == id:
					name = member['RemarkName'] if member['RemarkName'] else member['NickName']
			# 群友
			for member in self.GroupMemeberList:
				if member['UserName'] == id:
					name = member['DisplayName'] if member['DisplayName'] else member['NickName']

		if name == '未知群' or name == '陌生人': logging.debug(id)
		return name

	def getUSerID(self, name):
		for member in self.MemberList:
			if name == member['RemarkName'] or name == member['NickName']:
				return member
		return None

	def _showMsg(self, message):
		
		srcName = None
		dstName = None
		groupName = None
		content = None

		msg = message
		logging.debug(msg)

		if msg['raw_msg']: 
			srcName = self.getUserRemarkName(msg['raw_msg']['FromUserName'])
			dstName = self.getUserRemarkName(msg['raw_msg']['ToUserName'])
			content = msg['raw_msg']['Content'].replace('&lt;','<').replace('&gt;','>')
			message_id = msg['raw_msg']['MsgId']

			if content.find('http://weixin.qq.com/cgi-bin/redirectforward?args=') != -1:
				# 地理位置消息
				data = self._get(content).decode('gbk').encode('utf-8')
				pos = self._searchContent('title', data, 'xml')
				tree = html.fromstring(self._get(content))
				url = tree.xpath('//html/body/div/img')[0].attrib['src']

				for item in urlparse(url).query.split('&'):
					if item.split('=')[0] == 'center': loc = item.split('=')[-1:]

				content = '%s 发送了一个 位置消息 - 我在 [%s](%s) @ %s]' % (srcName, pos, url, loc)

			if msg['raw_msg']['ToUserName'] == 'filehelper':
				# 文件传输助手
				dstName = '文件传输助手'

			if msg['raw_msg']['FromUserName'][:2] == '@@':
				# 接收到来自群的消息
				if re.search(":<br/>", content, re.IGNORECASE):
					[people, content] = content.split(':<br/>')
					groupName = srcName
					srcName = self.getUserRemarkName(people)
					dstName = 'GROUP'
				else:
					groupName = srcName
					srcName = 'SYSTEM'
			elif msg['raw_msg']['ToUserName'][:2] == '@@':
				# 自己发给群的消息
				groupName = dstName
				dstName = 'GROUP'

			# 收到了红包
			if content == '收到红包，请在手机上查看': msg['message'] = content

			# 指定了消息内容
			if 'message' in msg.keys(): content = msg['message']

		
		if groupName != None:
			print '%s |%s| %s -> %s: %s' % (message_id, groupName.strip(), srcName.strip(), dstName.strip(), content.replace('<br/>','\n'))
			logging.info('%s |%s| %s -> %s: %s' % (message_id, groupName.strip(), srcName.strip(), dstName.strip(), content.replace('<br/>','\n')))
		else:
			print '%s %s -> %s: %s' % (message_id, srcName.strip(), dstName.strip(), content.replace('<br/>','\n'))
			logging.info('%s %s -> %s: %s' % (message_id, srcName.strip(), dstName.strip(), content.replace('<br/>','\n')))

	def handleMsg(self, r):
		for msg in r['AddMsgList']:
			#print '[*] 你有新的消息，请注意查收'
			#logging.debug('[*] 你有新的消息，请注意查收')

			if self.DEBUG:
				fn = 'msg' + str(int(random.random() * 1000)) + '.json'
				#with open(fn, 'w') as f: f.write(json.dumps(msg))
				#print '[*] 该消息已储存到文件: ' + fn
				#logging.debug('[*] 该消息已储存到文件: %s' % (fn))

			msgType = msg['MsgType']
			#name = self.getUserRemarkName(msg['FromUserName'])
			content = msg['Content'].replace('&lt;','<').replace('&gt;','>').replace('<br/>','').replace('<br />','')
			#msgid = msg['MsgId']			 
			user=self.getUserById(msg['FromUserName'])
			if user is None:
				print 'user is none'
				continue
			if content.find('http://mp.weixin.qq.com/')==-1:
				continue
			ename=user['Alias']
			username = user['NickName'];
			Signature = user['Signature'];
			print username
			if msgType == 49 and msg['AppMsgType']==5:
				items=content.split('<item>')				
				print len(items)
				i=0
				for item in items:
					i=i+1
					if i==1:
						continue
					itemtitle=self._searchContent('title', item, 'xml')
					itemurl=self._searchContent('url', item, 'xml')
					print 'itemtitle is '+itemtitle
					print 'itemurl is '+itemurl
					if itemtitle is None or len(itemtitle)<=2 or itemurl is None or len(itemurl)<=20:
						continue;
					self.addTopic(ename,username,Signature,itemtitle,itemurl)
			continue

			if msgType == 1:
				raw_msg = { 'raw_msg': msg }
				self._showMsg(raw_msg)
				if self.autoReplyMode:
					ans = self._xiaodoubi(content)+'\n[微信机器人自动回复]'
					if self.webwxsendmsg(ans, msg['FromUserName']):
						print '自动回复: '+ans
						logging.info('自动回复: '+ans)
					else:
						print '自动回复失败'
						logging.info('自动回复失败')
			elif msgType == 3:
				image = self.webwxgetmsgimg(msgid)
				raw_msg = { 'raw_msg': msg, 'message': '%s 发送了一张图片: %s' % (name, image) }
				self._showMsg(raw_msg)
				self._safe_open(image)
			elif msgType == 34:
				voice = self.webwxgetvoice(msgid)
				raw_msg = { 'raw_msg': msg, 'message': '%s 发了一段语音: %s' % (name, voice) }
				self._showMsg(raw_msg)
				self._safe_open(voice)
			elif msgType == 42:
				info = msg['RecommendInfo']
				print '%s 发送了一张名片:' % name
				print '========================='
				print '= 昵称: %s' % info['NickName']
				print '= 微信号: %s' % info['Alias']
				print '= 地区: %s %s' % (info['Province'], info['City'])
				print '= 性别: %s' % ['未知', '男', '女'][info['Sex']]
				print '========================='
				raw_msg = { 'raw_msg': msg, 'message': '%s 发送了一张名片: %s' % (name.strip(), json.dumps(info)) }
				self._showMsg(raw_msg)
			elif msgType == 47:
				url = self._searchContent('cdnurl', content)
				raw_msg = { 'raw_msg': msg, 'message': '%s 发了一个动画表情，点击下面链接查看: %s' % (name, url) }
				self._showMsg(raw_msg)
				self._safe_open(url)
			elif msgType == 49:
				appMsgType = defaultdict(lambda : "")
				appMsgType.update({5:'链接', 3:'音乐', 7:'微博'})
				print '%s 分享了一个%s:' % (name, appMsgType[msg['AppMsgType']])
				print '========================='
				print '= 标题: %s' % msg['FileName']
				print '= 描述: %s' % self._searchContent('des', content, 'xml')
				print '= 链接: %s' % msg['Url']
				print '= 来自: %s' % self._searchContent('appname', content, 'xml')
				print '========================='
				card = {
					'title': msg['FileName'],
					'description': self._searchContent('des', content, 'xml'),
					'url': msg['Url'],
					'appname': self._searchContent('appname', content, 'xml')
				}
				raw_msg = { 'raw_msg': msg, 'message': '%s 分享了一个%s: %s' % (name, appMsgType[msg['AppMsgType']], json.dumps(card)) }
				self._showMsg(raw_msg)
			elif msgType == 51:
				raw_msg = { 'raw_msg': msg, 'message': '[*] 成功获取联系人信息' }
				self._showMsg(raw_msg)
			elif msgType == 62:
				video = self.webwxgetvideo(msgid)
				raw_msg = { 'raw_msg': msg, 'message': '%s 发了一段小视频: %s' % (name, video) }
				self._showMsg(raw_msg)
				self._safe_open(video)
			elif msgType == 10002:
				raw_msg = { 'raw_msg': msg, 'message': '%s 撤回了一条消息' % name }
				self._showMsg(raw_msg)
			else:
				logging.debug('[*] 该消息类型为: %d，可能是表情，图片, 链接或红包: %s' % (msg['MsgType'], json.dumps(msg)))				
				raw_msg = { 'raw_msg': msg, 'message': '[*] 该消息类型为: %d，可能是表情，图片, 链接或红包' % msg['MsgType'] }
				self._showMsg(raw_msg)

	def listenMsgMode(self):
		print '[*] 进入消息监听模式 ... 成功'
		logging.debug('[*] 进入消息监听模式 ... 成功')
		self._run('[*] 进行同步线路测试 ... ', self.testsynccheck)
		playWeChat = 0
		redEnvelope = 0
		while True:
			self.lastCheckTs = time.time()
			[retcode, selector] = self.synccheck()
			if self.DEBUG: print 'retcode: %s, selector: %s' % (retcode, selector)
			logging.debug('retcode: %s, selector: %s' % (retcode, selector))
			if retcode == '1100':
				print '[*] 你在手机上登出了微信，债见'
				logging.debug('[*] 你在手机上登出了微信，债见')
				break
			if retcode == '1101':
				print '[*] 你在其他地方登录了 WEB 版微信，债见'
				logging.debug('[*] 你在其他地方登录了 WEB 版微信，债见')
				break	
			elif retcode == '0':
				if selector == '2':
					r = self.webwxsync()
					if r is not None: self.handleMsg(r)
				elif selector == '6':
					# TODO
					redEnvelope += 1
					#print '[*] 收到疑似红包消息 %d 次' % redEnvelope
					#logging.debug('[*] 收到疑似红包消息 %d 次' % redEnvelope)
				elif selector == '7':
					playWeChat += 1
					#print '[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat
					#logging.debug('[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat)
					r = self.webwxsync()
				elif selector == '0':
					time.sleep(2)
			if (time.time() - self.lastCheckTs) <= 20: time.sleep(time.time() - self.lastCheckTs)

	def sendMsg(self, name, word, isfile = False):
		id = self.getUSerID(name)
		if id:
			if isfile:
				with open(word, 'r') as f:
					for line in f.readlines():
						line = line.replace('\n','')
						self._echo('-> '+name+': '+line)
						if self.webwxsendmsg(line, id):
							print ' [成功]'
						else:
							print ' [失败]'
						time.sleep(1)
			else:
				if self.webwxsendmsg(word, id):
					print '[*] 消息发送成功'
					logging.debug('[*] 消息发送成功')
				else:
					print '[*] 消息发送失败'
					logging.debug('[*] 消息发送失败')
		else:
			print '[*] 此用户不存在'
			logging.debug('[*] 此用户不存在')

	def sendMsgToAll(self, word):
		for contact in self.ContactList:
			name = contact['RemarkName'] if contact['RemarkName'] else contact['NickName']
			id = contact['UserName']
			self._echo('-> '+name+': '+word)
			if self.webwxsendmsg(word, id):
				print ' [成功]'
			else:
				print ' [失败]'
			time.sleep(1)

	@catchKeyboardInterrupt
	def start(self):
		self.process()
		self._echo('[*] 微信网页版 ... 开动'); print; logging.debug('[*] 微信网页版 ... 开动')
		while True:
			self._run('[*] 正在获取 uuid ... ', self.getUUID)
			self._echo('[*] 正在获取二维码 ... 成功'); print; logging.debug('[*] 微信网页版 ... 开动'); self.genQRCode()
			print '[*] 请使用微信扫描二维码以登录 ... '
			if not self.waitForLogin():
				time.sleep(20)
				continue
				print '[*] 请在手机上点击确认以登录 ... '
			if not self.waitForLogin(0):
				time.sleep(20)
				continue
			break

		self._run('[*] 正在登录 ... ', self.login)
		self._run('[*] 微信初始化 ... ', self.webwxinit)
		self._run('[*] 开启状态通知 ... ', self.webwxstatusnotify)
		self._run('[*] 获取联系人 ... ', self.webwxgetcontact)
		self._echo('[*] 应有 %s 个联系人，读取到联系人 %d 个' % (self.MemberCount, len(self.MemberList))); print
		self._echo('[*] 共有 %d 个群 | %d 个直接联系人 | %d 个特殊账号 ｜ %d 公众号或服务号' % (len(self.GroupList), len(self.ContactList), len(self.SpecialUsersList), len(self.PublicUsersList) )); print
		self._run('[*] 获取群 ... ', self.webwxbatchgetcontact)		
		logging.debug('[*] 微信网页版 ... 开动')
		if self.DEBUG: print self
		logging.debug(self)

		if self.interactive and raw_input('[*] 是否开启自动回复模式(y/n): ') == 'y':
			self.autoReplyMode = True
			print '[*] 自动回复模式 ... 开启'
			logging.debug('[*] 自动回复模式 ... 开启')
		else:
			print '[*] 自动回复模式 ... 关闭'
			logging.debug('[*] 自动回复模式 ... 关闭')

		listenProcess = multiprocessing.Process(target=self.listenMsgMode)
		listenProcess.start()

		while True:
			text = raw_input('')
			if text == 'quit':
				listenProcess.terminate()
				print('[*] 退出微信')
				logging.debug('[*] 退出微信')
				exit()
			elif text[:2] == '->':
				[name, word] = text[2:].split(':')
				if name == 'all': self.sendMsgToAll(word)
				else: self.sendMsg(name, word)
			elif text[:3] == 'm->':
				[name, file] = text[3:].split(':')
				self.sendMsg(name, file, True)
			elif text[:3] == 'f->':
				print '发送文件'
				logging.debug('发送文件')
			elif text[:3] == 'i->':
				print '发送图片'
				logging.debug('发送图片')

	def _safe_open(self, path):
		if self.autoOpen:
			if platform.system() == "Linux":
			    os.system("xdg-open %s &" % path)
			else:
				os.system('open %s &' % path)

	def _run(self, str, func, *args):
		self._echo(str)
		if func(*args): print '成功'; logging.debug('%s... 成功' % (str))
		else: print('失败\n[*] 退出程序'); logging.debug('%s... 失败' % (str)); logging.debug('[*] 退出程序'); exit()

	def _echo(self, str):
		sys.stdout.write(str)
		sys.stdout.flush()

	def _printQR(self, mat):
		for i in mat:
			BLACK = '\033[40m  \033[0m'
			WHITE = '\033[47m  \033[0m'
			print ''.join([BLACK if j else WHITE for j in i])

	def _str2qr(self, qrstr):
		qr = qrcode.QRCode()
		qr.border = 1
		qr.version=1
		qr.add_data(qrstr) 
		qr.make(fit=True)

		rdm=random.randint(1, 100)
		filename='/nodeclub/public/qr/login'+str(rdm)+'.png'		 
		if os.path.exists(filename):
			os.remove(filename)
		img = qr.make_image()
		img.save(filename)		

		mat = qr.get_matrix()		
		self._printQR(mat) # qr.print_tty() or qr.print_ascii()
		print 'qr img url: '+filename

	def _transcoding(self, data):
		if not data: return data
		result = None
		if type(data) == unicode:
			result = data
		elif type(data) == str:
			result = data.decode('utf-8')
		return result

	def _get(self, url, api=None):
		request = urllib2.Request(url = url)
		request.add_header('Referer', 'https://wx.qq.com/')
		if api == 'webwxgetvoice': request.add_header('Range', 'bytes=0-')
		if api == 'webwxgetvideo': request.add_header('Range', 'bytes=0-')
		response = urllib2.urlopen(request)
		data = response.read()
		logging.debug(url)
		return data

	def _post(self, url, params, jsonfmt = True):
		if jsonfmt:
			request = urllib2.Request(url = url, data = json.dumps(params))
			request.add_header('ContentType', 'application/json; charset=UTF-8')
		else:
			request = urllib2.Request(url = url, data = urllib.urlencode(params))
		response = urllib2.urlopen(request)
		data = response.read()
		if jsonfmt: return json.loads(data, object_hook=_decode_dict)
		return data

	def _xiaodoubi(self, word):
		url = 'http://www.xiaodoubi.com/bot/chat.php'
		try:
			r = requests.post(url, data = {'chat': word})
			return r.content
		except:
			return "让我一个人静静 T_T..."

	def _simsimi(self, word):
		key = ''
		url = 'http://sandbox.api.simsimi.com/request.p?key=%s&lc=ch&ft=0.0&text=%s' % (key, word)
		r = requests.get(url)
		ans = r.json()
		if ans['result'] == '100': return ans['response']
		else: return '你在说什么，风太大听不清列'

	def _searchContent(self, key, content, fmat = 'attr'):
		if fmat == 'attr':
			pm = re.search(key+'\s?=\s?"([^"<]+)"', content)
			if pm: return pm.group(1)
		elif fmat == 'xml':
			pm = re.search('<{0}>([^<]+)</{0}>'.format(key),content)
			if not pm: pm = re.search('<{0}><\!\[CDATA\[(.*?)\]\]></{0}>'.format(key),content)
			if pm: return pm.group(1)
		return '未知'
	def process(self): 
		connection=MongoClient('127.0.0.1', 27017)
		global topics
		topics = connection.dyx.topics
		global users
		users=connection.dyx.users
	def GetNowTime(self):
		return time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(int(time.time()-28800)))
	def insertTopic(self,author_id,content,title,tab):
		sendtime=datetime.datetime.strptime(self.GetNowTime(),'%Y-%m-%d %H:%M:%S') 
		datas=[{"__v":0,"author_id":author_id,"tab":tab,"content":content,
		"title":title,"deleted":False,
		"last_reply_at":sendtime,"update_at":sendtime,"create_at":sendtime,
		"collect_count":0,"visit_count":0,"reply_count":0,"lock":False,
		"good":False,"top":False,"issend":0}]
		#print datas;
		topics.insert(datas)
	def insertUser(self,weixinEName,weixinName,Signature):
		sendtime=datetime.datetime.strptime(self.GetNowTime(),'%Y-%m-%d %H:%M:%S') 
		tab=self.getTab(Signature);
		try:
			self.downimgbyfilename(weixinEName)
		except Exception,e:
			print str(e)
		newuser=[{"loginname":weixinEName,"active":True,"name":weixinName,
			"email":str(int(time.time()))+"@dianxiaoyue.com",
			"accessToken":str(uuid.uuid1()),"avatar":"/public/img/"+weixinEName+".jpg",
			"pass":"$2a$10$6.XBCgvurt2QHJsBy9poMeBvF0VDJXMpJ9a6w935Ufz0eYk8tojTO",
			"collect_tag_count":0,"collect_topic_count":0,"create_at":sendtime,
			"Signature":Signature,"tab":tab,"following_count":0,"is_block":False,
			"receive_at_mail":False,"receive_reply_mail":False,"reply_count":0,
			"score":10,"topic_count":10,"update_at":sendtime}];
		users.insert(newuser)
	def getTab(self,Signature):
		tab = "yc";
		if Signature.find("电影")>=0 or Signature.find("音乐")>=0 or Signature.find("大片")>=0:
			tab = "movie"
		elif Signature.find("美食")>=0 or Signature.find("饮食")>=0 or Signature.find("健身")>=0:
			tab = "food"
		elif Signature.find("汽车")>=0:
			tab = "auto"
		elif Signature.find("编程")>=0 or Signature.find("前端")>=0 or Signature.find("代码")>=0:
			tab = "code"
		elif Signature.find("历史")>=0 or Signature.find("书")>=0 or Signature.find("文艺")>=0:
			tab = "reedbook"
		elif Signature.find("科技")>=0 or Signature.find("技术")>=0:
			tab = "tech"
		elif Signature.find("搞笑")>=0 or Signature.find("笑话")>=0 or Signature.find("娱乐")>=0:
			tab = "fun"
		elif Signature.find("时尚")>=0 or Signature.find("生活")>=0:
			tab = "life"
		elif Signature.find("新闻")>=0 or Signature.find("资讯")>=0:
			tab = "news"
		return tab
	def downimgbyfilename(self,filename):
		localpath="/nodeclub/public/img/"+filename+".jpg"
		if os.path.exists(localpath):
			return
		url="https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxgeticon?username="+filename
		request = urllib2.Request(url = url)
		request.add_header('Referer', 'https://wx.qq.com/')
		
		of=open(localpath, 'w+b')
		q= urllib2.urlopen(request)
		of.write(q.read())
		q.close()
		of.clos	
		localpath="/nodeclub/public/qr/"+filename+".jpg"
		if os.path.exists(localpath):
			return
		url="http://open.weixin.qq.com/qr/code/?username="+filename
		request = urllib2.Request(url = url)
		request.add_header('Referer', 'https://wx.qq.com/')
		of=open(localpath, 'w+b')
		q= urllib2.urlopen(request)
		of.write(q.read())
		q.close()
		of.close()
	def addTopic(self,weixinEName,weixinName,Signature,title,body):
		user=users.find_one({'loginname':weixinEName})
		if not user:
			self.insertUser(weixinEName,weixinName,Signature)
			user=users.find_one({'loginname':weixinEName})
		existstitle=topics.find({'title':title})
		if existstitle and existstitle.count() > 0:
			print "title exist"
			return		
		tab=user["tab"]
		if not tab:
			tab=self.getTab(Signature)
			users.update({'loginname':weixinEName},{'$set':{"tab":tab}},False,False)
		print "[#] insert topic "+ title
		self.insertTopic(user["_id"],body,title,tab);
class UnicodeStreamFilter:
	def __init__(self, target):
		self.target = target
		self.encoding = 'utf-8'
		self.errors = 'replace'
		self.encode_to = self.target.encoding

	def write(self, s):
		if type(s) == str:
			s = s.decode('utf-8')
		s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
		self.target.write(s)

	def flush(self):
		self.target.flush()

if sys.stdout.encoding == 'cp936':
	sys.stdout = UnicodeStreamFilter(sys.stdout)


if __name__ == '__main__':

	logger = logging.getLogger(__name__)
	#import coloredlogs
	#coloredlogs.install(level='DEBUG')

	webwx = WebWeixin()
	webwx.start()
