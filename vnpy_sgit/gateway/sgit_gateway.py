from pathlib import Path
import sys
import pytz
from datetime import datetime
from typing import Any, Dict, List

from ..api import (
    MdApi,
    TdApi,
    THOST_FTDC_OAS_Submitted,
    THOST_FTDC_OAS_Accepted,
    THOST_FTDC_OAS_Rejected,
    THOST_FTDC_OST_NoTradeQueueing,
    THOST_FTDC_OST_PartTradedQueueing,
    THOST_FTDC_OST_AllTraded,
    THOST_FTDC_OST_Canceled,
    THOST_FTDC_D_Buy,
    THOST_FTDC_D_Sell,
    THOST_FTDC_PD_Long,
    THOST_FTDC_PD_Short,
    THOST_FTDC_OPT_LimitPrice,
    THOST_FTDC_OPT_AnyPrice,
    THOST_FTDC_OF_Open,
    THOST_FTDC_OFEN_Close,
    THOST_FTDC_OFEN_CloseYesterday,
    THOST_FTDC_OFEN_CloseToday,
    THOST_FTDC_PC_Futures,
    THOST_FTDC_PC_Options,
    THOST_FTDC_PC_SpotOption,
    THOST_FTDC_PC_Combination,
    THOST_FTDC_CP_CallOptions,
    THOST_FTDC_CP_PutOptions,
    THOST_FTDC_HF_Speculation,
    THOST_FTDC_CC_Immediately,
    THOST_FTDC_FCC_NotForceClose,
    THOST_FTDC_TC_GFD,
    THOST_FTDC_VC_AV,
    THOST_FTDC_TC_IOC,
    THOST_FTDC_VC_CV,
    THOST_FTDC_AF_Delete
)
from vnpy.event.engine import Event
from vnpy.trader.constant import (
    Direction,
    Offset,
    Exchange,
    OrderType,
    Product,
    Status,
    OptionType
)
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
)
from vnpy.trader.utility import get_folder_path
from vnpy.trader.event import EVENT_TIMER

# 委托状态映射
STATUS_SGIT2VT: Dict[str, Status] = {
    THOST_FTDC_OAS_Submitted: Status.SUBMITTING,
    THOST_FTDC_OAS_Accepted: Status.SUBMITTING,
    THOST_FTDC_OAS_Rejected: Status.REJECTED,
    THOST_FTDC_OST_NoTradeQueueing: Status.NOTTRADED,
    THOST_FTDC_OST_PartTradedQueueing: Status.PARTTRADED,
    THOST_FTDC_OST_AllTraded: Status.ALLTRADED,
    THOST_FTDC_OST_Canceled: Status.CANCELLED
}

# 多空方向映射
DIRECTION_VT2SGIT: Dict[Direction, str] = {
    Direction.LONG: THOST_FTDC_D_Buy,
    Direction.SHORT: THOST_FTDC_D_Sell
}
DIRECTION_SGIT2VT: Dict[str, Direction] = {v: k for k, v in DIRECTION_VT2SGIT.items()}
DIRECTION_SGIT2VT[THOST_FTDC_PD_Long] = Direction.LONG
DIRECTION_SGIT2VT[THOST_FTDC_PD_Short] = Direction.SHORT

# 委托类型映射
ORDERTYPE_VT2SGIT: Dict[OrderType, str] = {
    OrderType.LIMIT: THOST_FTDC_OPT_LimitPrice,
    OrderType.MARKET: THOST_FTDC_OPT_AnyPrice
}
ORDERTYPE_SGIT2VT: Dict[str, OrderType] = {v: k for k, v in ORDERTYPE_VT2SGIT.items()}

# 开平方向映射
OFFSET_VT2SGIT: Dict[Offset, str] = {
    Offset.OPEN: THOST_FTDC_OF_Open,
    Offset.CLOSE: THOST_FTDC_OFEN_Close,
    Offset.CLOSETODAY: THOST_FTDC_OFEN_CloseToday,
    Offset.CLOSEYESTERDAY: THOST_FTDC_OFEN_CloseYesterday,
}
OFFSET_SGIT2VT: Dict[str, Offset] = {v: k for k, v in OFFSET_VT2SGIT.items()}

# 交易所映射
EXCHANGE_SGIT2VT: Dict[str, Exchange] = {
    "CFFEX": Exchange.CFFEX,
    "SHFE": Exchange.SHFE,
    "CZCE": Exchange.CZCE,
    "DCE": Exchange.DCE,
    "INE": Exchange.INE,
    "GOLD": Exchange.SGE,
    "PAT": Exchange.SMART,
    "LTS": Exchange.SMART,
    "CME": Exchange.CME,
    "LME": Exchange.LME,
    "SGE": Exchange.SGE,
    "HKEX": Exchange.HKFE,

}

# 产品类型映射
PRODUCT_SGIT2VT: Dict[str, Product] = {
    THOST_FTDC_PC_Futures: Product.FUTURES,
    THOST_FTDC_PC_Options: Product.OPTION,
    THOST_FTDC_PC_SpotOption: Product.OPTION,
    THOST_FTDC_PC_Combination: Product.SPREAD
}

# 期权类型映射
OPTIONTYPE_SGIT2VT: Dict[str, OptionType] = {
    THOST_FTDC_CP_CallOptions: OptionType.CALL,
    THOST_FTDC_CP_PutOptions: OptionType.PUT
}

# 其他常量
MAX_FLOAT: float = sys.float_info.max
CHINA_TZ = pytz.timezone("Asia/Shanghai")

# 全局缓存字典
symbol_exchange_map: Dict[str, Exchange] = {}
symbol_name_map: Dict[str, str] = {}
symbol_size_map: Dict[str, float] = {}


class SgitGateway(BaseGateway):
    """
    vn.py用于对接飞鼠的接口。
    """

    default_setting: Dict[str, str] = {
        "用户名": "",
        "密码": "",
        "交易服务器": "",
        "行情服务器": "",
        "产品名称": "",
        "授权编码": ""
    }

    exchanges: List[Exchange] = list(EXCHANGE_SGIT2VT.values())

    def __init__(self, event_engine):
        """构造函数"""
        super().__init__(event_engine, "SGIT")

        self.td_api: "SgitTdApi" = SgitTdApi(self)
        self.md_api: "SgitMdApi" = SgitMdApi(self)

    def connect(self, setting: dict) -> None:
        """连接交易接口"""
        userid: str = setting["用户名"]
        password: str = setting["密码"]
        td_address: str = setting["交易服务器"]
        md_address: str = setting["行情服务器"]
        appid: str = setting["产品名称"]
        auth_code: str = setting["授权编码"]

        if not td_address.startswith("tcp://"):
            td_address: str = "tcp://" + td_address

        if not md_address.startswith("tcp://"):
            md_address: str = "tcp://" + md_address

        self.td_api.connect(td_address, userid, password, auth_code, appid)
        self.md_api.connect(md_address, userid, password)

        self.init_query()

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        self.md_api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        """委托下单"""
        return self.td_api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """委托撤单"""
        self.td_api.cancel_order(req)

    def query_account(self) -> None:
        """查询资金"""
        self.td_api.query_account()

    def query_position(self) -> None:
        """查询持仓"""
        self.td_api.query_position()

    def close(self) -> None:
        """关闭接口"""
        self.td_api.close()
        self.md_api.close()

    def write_error(self, msg: str, error: dict) -> None:
        """输出错误信息日志"""
        error_id: str = error["ErrorID"]
        error_msg: str = error["ErrorMsg"]
        msg: str = f"{msg}，代码：{error_id}，信息：{error_msg}"
        self.write_log(msg)

    def process_timer_event(self, event: Event) -> None:
        """定时事件处理"""
        self.count += 1
        if self.count < 2:
            return
        self.count: int = 0

        func = self.query_functions.pop(0)
        func()
        self.query_functions.append(func)

    def init_query(self) -> None:
        """初始化查询任务"""
        self.count: int = 0
        self.query_functions = [self.query_account, self.query_position]
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)


class SgitMdApi(MdApi):
    """飞鼠行情API"""

    def __init__(self, gateway: SgitGateway) -> None:
        """构造函数"""
        super().__init__()

        self.gateway: SgitGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.reqid: int = 0

        self.connect_status: bool = False
        self.login_status: bool = False
        self.subscribed: set = set()

        self.userid: str = ""
        self.password: str = ""
        self.brokerid: str = ""

    def onFrontConnected(self) -> None:
        """服务器连接成功回报"""
        self.gateway.write_log("行情服务器连接成功")
        self.login()

    def onFrontDisconnected(self, reason: int) -> None:
        """服务器连接断开回报"""
        self.login_status: bool = False
        self.gateway.write_log(f"行情服务器连接断开，原因{reason}")

    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """用户登录请求回报"""
        if not error["ErrorID"]:
            self.login_status: bool = True
            self.gateway.write_log("行情服务器登录成功")

            for symbol in self.subscribed:
                self.subscribeMarketData(symbol)
        else:
            self.gateway.write_error("行情服务器登录失败", error)

    def onRspError(self, error: dict, reqid: int, last: bool) -> None:
        """请求报错回报"""
        self.gateway.write_error("行情接口报错", error)

    def onRspSubMarketData(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """订阅行情回报"""
        if not error or not error["ErrorID"]:
            return

        self.gateway.write_error("行情订阅失败", error)

    def onRtnDepthMarketData(self, data: dict) -> None:
        """行情数据推送"""
        symbol: str = data["InstrumentID"]
        exchange: Exchange = symbol_exchange_map.get(symbol, "")
        if not exchange:
            return

        timestamp: str = f"{data['TradingDay']} {data['UpdateTime']}.{int(data['UpdateMillisec']/100)}"
        dt: datetime = datetime.strptime(timestamp, "%Y%m%d %H:%M:%S.%f")
        dt: datetime = CHINA_TZ.localize(dt)

        tick: TickData = TickData(
            symbol=symbol,
            exchange=exchange,
            datetime=dt,
            name=symbol_name_map[symbol],
            volume=data["Volume"],
            open_interest=data["OpenInterest"],
            last_price=data["LastPrice"],
            limit_up=data["UpperLimitPrice"],
            limit_down=data["LowerLimitPrice"],
            open_price=adjust_price(data["OpenPrice"]),
            high_price=adjust_price(data["HighestPrice"]),
            low_price=adjust_price(data["LowestPrice"]),
            pre_close=adjust_price(data["PreClosePrice"]),
            bid_price_1=adjust_price(data["BidPrice1"]),
            ask_price_1=adjust_price(data["AskPrice1"]),
            bid_volume_1=data["BidVolume1"],
            ask_volume_1=data["AskVolume1"],
            gateway_name=self.gateway_name
        )

        if data["BidVolume2"] or data["AskVolume2"]:
            tick.bid_price_2 = adjust_price(data["BidPrice2"])
            tick.bid_price_3 = adjust_price(data["BidPrice3"])
            tick.bid_price_4 = adjust_price(data["BidPrice4"])
            tick.bid_price_5 = adjust_price(data["BidPrice5"])

            tick.ask_price_2 = adjust_price(data["AskPrice2"])
            tick.ask_price_3 = adjust_price(data["AskPrice3"])
            tick.ask_price_4 = adjust_price(data["AskPrice4"])
            tick.ask_price_5 = adjust_price(data["AskPrice5"])

            tick.bid_volume_2 = adjust_price(data["BidVolume2"])
            tick.bid_volume_3 = adjust_price(data["BidVolume3"])
            tick.bid_volume_4 = adjust_price(data["BidVolume4"])
            tick.bid_volume_5 = adjust_price(data["BidVolume5"])

            tick.ask_volume_2 = adjust_price(data["AskVolume2"])
            tick.ask_volume_3 = adjust_price(data["AskVolume3"])
            tick.ask_volume_4 = adjust_price(data["AskVolume4"])
            tick.ask_volume_5 = adjust_price(data["AskVolume5"])

        self.gateway.on_tick(tick)

    def connect(self, address: str, userid: str, password: str) -> None:
        """连接服务器"""
        self.userid: str = userid
        self.password: str = password

        # 未连接状态下开始连接
        if not self.connect_status:
            path: Path = get_folder_path(self.gateway_name.lower())
            self.createFtdcMdApi(str(path) + "\\Md")

            self.registerFront(address)
            self.init()

            self.connect_status = True

        # 已连接状态下立即登录
        elif not self.login_status:
            self.login()

    def login(self) -> None:
        """用户登录"""
        req: dict = {
            "UserID": self.userid,
            "Password": self.password,
            "BrokerID": self.brokerid
        }

        self.reqid += 1
        self.reqUserLogin(req, self.reqid)

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        if self.login_status:
            self.subscribeMarketData(req.symbol)
        self.subscribed.add(req.symbol)

    def close(self) -> None:
        """关闭连接"""
        if self.connect_status:
            self.exit()


class SgitTdApi(TdApi):
    """飞鼠交易API"""

    def __init__(self, gateway: SgitGateway) -> None:
        """构造函数"""
        super().__init__()

        self.gateway: SgitGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.reqid: int = 0
        self.order_ref: int = 0

        self.connect_status: bool = False
        self.login_status: bool = False
        self.auth_status: bool = False
        self.login_failed: bool = False

        self.userid: str = ""
        self.password: str = ""
        self.brokerid: str = ""
        self.auth_code: str = ""
        self.appid: str = ""
        self.product_info: str = ""
        self.sge_investor: str = ""

        self.order_data: List[dict] = []
        self.trade_data: List[dict] = []
        self.positions: Dict[str, PositionData] = {}
        self.sysid_orderid_map: Dict[str, str] = {}

    def onFrontConnected(self) -> None:
        """服务器连接成功回报"""
        self.gateway.write_log("交易服务器连接成功")

        if self.auth_code:
            self.authenticate()
        else:
            self.login()

    def onFrontDisconnected(self, reason: int) -> None:
        """服务器连接断开回报"""
        self.login_status: bool = False
        self.gateway.write_log(f"交易服务器连接断开，原因{reason}")

    def onRspAuthenticate(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """用户授权验证回报"""
        if not error['ErrorID']:
            self.auth_status: bool = True
            self.gateway.write_log("交易服务器授权验证成功")
            self.login()
        else:
            self.gateway.write_error("交易服务器授权验证失败", error)

    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """用户登录请求回报"""
        if not error["ErrorID"]:
            self.login_status: bool = True
            self.gateway.write_log("交易服务器登录成功")

            # 更新订单ref
            if data["MaxOrderRef"]:
                self.order_ref: int = max(self.order_ref, int(data["MaxOrderRef"]))

            # 结算信息确认
            req: dict = {
                "BrokerID": self.brokerid,
                "InvestorID": self.userid
            }
            self.reqid += 1
            self.reqSettlementInfoConfirm(req, self.reqid)
        else:
            self.login_failed: bool = True

            self.gateway.write_error("交易服务器登录失败", error)

    def onRspOrderInsert(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """委托下单失败回报"""
        if error["ErrorID"] == 0:
            return

        self.gateway.write_error("交易委托失败", error)

        orderid: str = data["OrderRef"]
        self.order_ref: int = max(self.order_ref, int(orderid))

        symbol: str = data["InstrumentID"]
        exchange: Exchange = symbol_exchange_map.get(symbol, None)
        if not exchange:
            return

        order: OrderData = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            direction=DIRECTION_SGIT2VT[data["Direction"]],
            offset=OFFSET_SGIT2VT.get(data["CombOffsetFlag"], Offset.NONE),
            price=data["LimitPrice"],
            volume=data["VolumeTotalOriginal"],
            status=Status.REJECTED,
            gateway_name=self.gateway_name
        )
        self.gateway.on_order(order)

    def onRspOrderAction(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """委托撤单失败回报"""
        if error["ErrorID"] != 0:
            self.gateway.write_error("交易撤单失败", error)

    def onRspQueryMaxOrderVolume(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """查询最大报单数量响应"""
        pass

    def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """结算信息确认回报"""
        self.gateway.write_log("结算信息确认成功")

        self.reqid += 1
        self.reqQryInstrument({}, self.reqid)

    def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """持仓查询回报"""
        if not data:
            return

        # 检查合约信息
        if data["InstrumentID"] in symbol_exchange_map:
            # 获取缓存持仓
            key: str = f"{data['InstrumentID'], data['PosiDirection']}"
            position: PositionData = self.positions.get(key, None)
            if not position:
                position: PositionData = PositionData(
                    symbol=data["InstrumentID"],
                    exchange=symbol_exchange_map[data["InstrumentID"]],
                    direction=DIRECTION_SGIT2VT[data["PosiDirection"]],
                    gateway_name=self.gateway_name
                )
                self.positions[key] = position

            # 更新SHFE和INE持仓
            if position.exchange in [Exchange.SHFE, Exchange.INE]:
                if data["YdPosition"] and not data["TodayPosition"]:
                    position.yd_volume = data["Position"]
            # 更新其他交易所持仓
            else:
                position.yd_volume = data["Position"] - data["TodayPosition"]

            # 获得合约乘数，差价合约没有乘数
            size: float = symbol_size_map.get(position.symbol, 0)

            # 计算之前的持仓价
            cost: float = position.price * position.volume * size

            # 更新新的持仓数量
            position.volume += data["Position"]
            position.pnl += data["PositionProfit"]

            # 计算持仓均价
            if position.volume and size:
                cost += data["PositionCost"] * data["Position"] * size
                position.price = cost / (position.volume * size)

            # 获取冻结量
            if position.direction == Direction.LONG:
                position.frozen += data["ShortFrozen"]
            else:
                position.frozen += data["LongFrozen"]

        if last:
            for position in self.positions.values():
                self.gateway.on_position(position)

            self.positions.clear()

    def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """请求查询资金账户响应"""
        if "AccountID" not in data:
            return

        account: AccountData = AccountData(
            accountid=data["AccountID"],
            balance=data["Balance"],
            frozen=data["FrozenMargin"] + data["FrozenCash"] + data["FrozenCommission"],
            gateway_name=self.gateway_name
        )
        account.available = data["Available"]

        self.gateway.on_account(account)

    def onRspQryInstrument(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """合约查询回报"""
        if data:
            product: Product = PRODUCT_SGIT2VT.get(data["ProductClass"], None)

            contract: ContractData = ContractData(
                symbol=data["InstrumentID"],
                exchange=EXCHANGE_SGIT2VT[data["ExchangeID"]],
                name=data["InstrumentName"],
                product=product,
                size=data["VolumeMultiple"],
                pricetick=data["PriceTick"],
                gateway_name=self.gateway_name
            )

            # 期权
            if contract.product == Product.OPTION:
                # 移除CZCE期权C/P后缀
                if contract.exchange == Exchange.CZCE:
                    contract.option_portfolio = data["ProductID"][:-1]
                else:
                    contract.option_portfolio = data["ProductID"]

                contract.option_underlying = data["UnderlyingInstrID"]
                contract.option_type = OPTIONTYPE_SGIT2VT.get(data["OptionsType"], None)
                contract.option_strike = data["StrikePrice"]
                contract.option_index = str(data["StrikePrice"])
                contract.option_expiry = datetime.strptime(data["ExpireDate"], "%Y%m%d")

            self.gateway.on_contract(contract)

            symbol_exchange_map[contract.symbol] = contract.exchange
            symbol_name_map[contract.symbol] = contract.name
            symbol_size_map[contract.symbol] = contract.size

        if last:
            self.gateway.write_log("合约信息查询成功")

            for data in self.order_data:
                self.onRtnOrder(data)
            self.order_data.clear()

            for data in self.trade_data:
                self.onRtnTrade(data)
            self.trade_data.clear()

    def onRtnOrder(self, data: dict) -> None:
        """订单更新推送"""
        symbol: str = data["InstrumentID"]
        exchange: Exchange = symbol_exchange_map.get(symbol, "")
        if not exchange:
            self.order_data.append(data)
            return

        orderid: str = data["OrderRef"]
        self.order_ref = max(self.order_ref, int(orderid))

        timestamp: str = f"{data['InsertDate']} {data['InsertTime']}"
        dt: datetime = datetime.strptime(timestamp, "%Y%m%d %H:%M:%S")
        dt: datetime = CHINA_TZ.localize(dt)

        order: OrderData = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            type=ORDERTYPE_SGIT2VT[data["OrderPriceType"]],
            direction=DIRECTION_SGIT2VT[data["Direction"]],
            offset=OFFSET_SGIT2VT[data["CombOffsetFlag"]],
            price=data["LimitPrice"],
            volume=data["VolumeTotalOriginal"],
            traded=data["VolumeTraded"],
            status=STATUS_SGIT2VT[data["OrderStatus"]],
            datetime=dt,
            gateway_name=self.gateway_name
        )
        self.gateway.on_order(order)

        self.sysid_orderid_map[data["OrderSysID"]] = orderid

    def onRtnTrade(self, data: dict) -> None:
        """成交更新推送"""
        symbol: str = data["InstrumentID"]
        exchange: Exchange = symbol_exchange_map.get(symbol, "")
        if not exchange:
            self.trade_data.append(data)
            return

        orderid: str = self.sysid_orderid_map[data["OrderSysID"]]

        timestamp: str = f"{data['TradeDate']} {data['TradeTime']}"
        dt: datetime = datetime.strptime(timestamp, "%Y%m%d %H:%M:%S")
        dt: datetime = CHINA_TZ.localize(dt)

        trade: TradeData = TradeData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            tradeid=data["TradeID"],
            direction=DIRECTION_SGIT2VT[data["Direction"]],
            offset=OFFSET_SGIT2VT[data["OffsetFlag"]],
            price=data["Price"],
            volume=data["Volume"],
            datetime=dt,
            gateway_name=self.gateway_name
        )

        self.gateway.on_trade(trade)

    def connect(
        self,
        address: str,
        userid: str,
        password: str,
        auth_code: str,
        appid: str
    ) -> None:
        """连接服务器"""
        self.userid: str = userid
        self.password: str = password
        self.auth_code: str = auth_code
        self.appid: str = appid
        self.sge_investor: str = userid.replace("08", "06")

        if not self.connect_status:
            path: Path = get_folder_path(self.gateway_name.lower())
            self.createFtdcTraderApi(str(path) + "\\Td")

            self.subscribePrivateTopic(0)
            self.subscribePublicTopic(0)

            self.registerFront(address)
            self.init()

            self.connect_status: bool = True
        else:
            self.authenticate()

    def authenticate(self) -> None:
        """发起授权验证"""
        req: dict = {
            "UserID": self.userid,
            "BrokerID": self.brokerid,
            "AuthCode": self.auth_code,
            "AppID": self.appid
        }

        if self.product_info:
            req["UserProductInfo"] = self.product_info

        self.reqid += 1
        self.reqAuthenticate(req, self.reqid)

    def login(self) -> None:
        """用户登录"""
        if self.login_failed:
            return

        req: dict = {
            "UserID": self.userid,
            "Password": self.password,
            "BrokerID": self.brokerid,
            "AppID": self.appid
        }

        if self.product_info:
            req["UserProductInfo"] = self.product_info

        self.reqid += 1
        self.reqUserLogin(req, self.reqid)

    def send_order(self, req: OrderRequest) -> str:
        """委托下单"""
        if req.offset not in OFFSET_VT2SGIT:
            self.gateway.write_log("请选择开平方向")
            return ""

        self.order_ref += 1
        orderid: str = str(self.order_ref).rjust(12, "0")

        sgit_req: dict = {
            "InstrumentID": req.symbol,
            "ExchangeID": req.exchange.value,
            "LimitPrice": req.price,
            "VolumeTotalOriginal": int(req.volume),
            "OrderPriceType": ORDERTYPE_VT2SGIT.get(req.type, ""),
            "Direction": DIRECTION_VT2SGIT.get(req.direction, ""),
            "CombOffsetFlag": OFFSET_VT2SGIT.get(req.offset, ""),
            "OrderRef": orderid,
            "UserID": self.userid,
            "BrokerID": self.brokerid,
            "CombHedgeFlag": THOST_FTDC_HF_Speculation,
            "ContingentCondition": THOST_FTDC_CC_Immediately,
            "ForceCloseReason": THOST_FTDC_FCC_NotForceClose,
            "IsAutoSuspend": 0,
            "TimeCondition": THOST_FTDC_TC_GFD,
            "VolumeCondition": THOST_FTDC_VC_AV,
            "MinVolume": 1
        }

        # 不同交易所使用不同投资人id
        if req.exchange == Exchange.SGE:
            sgit_req["InvestorID"] = self.sge_investor
        else:
            sgit_req["InvestorID"] = self.userid

        if req.type == OrderType.FAK:
            sgit_req["OrderPriceType"] = THOST_FTDC_OPT_LimitPrice
            sgit_req["TimeCondition"] = THOST_FTDC_TC_IOC
            sgit_req["VolumeCondition"] = THOST_FTDC_VC_AV
        elif req.type == OrderType.FOK:
            sgit_req["OrderPriceType"] = THOST_FTDC_OPT_LimitPrice
            sgit_req["TimeCondition"] = THOST_FTDC_TC_IOC
            sgit_req["VolumeCondition"] = THOST_FTDC_VC_CV

        self.reqid += 1
        self.reqOrderInsert(sgit_req, self.reqid)

        order: OrderData = req.create_order_data(orderid, self.gateway_name)
        self.gateway.on_order(order)

        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """委托撤单"""
        sgit_req: dict = {
            "InstrumentID": req.symbol,
            "ExchangeID": req.exchange.value,
            "OrderRef": req.orderid,
            "ActionFlag": THOST_FTDC_AF_Delete,
            "BrokerID": self.brokerid,
            "InvestorID": self.userid,
        }

        self.reqid += 1
        self.reqOrderAction(sgit_req, self.reqid)

    def query_account(self) -> None:
        """查询资金"""
        self.reqid += 1
        self.reqQryTradingAccount({}, self.reqid)

    def query_position(self) -> None:
        """查询持仓"""
        if not symbol_exchange_map:
            return

        self.reqid += 1
        self.reqQryInvestorPosition({}, self.reqid)

    def close(self) -> None:
        """关闭连接"""
        if self.connect_status:
            self.exit()


def adjust_price(price: float) -> float:
    """将异常的浮点数最大值（MAX_FLOAT）数据调整为0"""
    if price == MAX_FLOAT:
        price = 0
    return price
