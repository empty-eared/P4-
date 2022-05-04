 #!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.switch import ShutdownAllSwitchConnections

def writeTunnelRules(p4info_helper, ingress_sw,
                    dst_eth_addr,dst_ip_addr,port,number):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, number)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "port": port,
            "dstAddr":dst_eth_addr
        })
    ingress_sw.WriteTableEntry(table_entry)
    print("Installed ingress tunnel rule on %s" % ingress_sw.name)

def readTableRules(p4info_helper, sw):
    """
    :param p4info_helper: the P4Info helper
    :param sw: 转换连接
    """
    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            table_name = p4info_helper.get_tables_name(entry.table_id)                  # 获取表的名字
            action = p4info_helper.get_actions_name(entry.action.action.action_id)      # 获取动作名字
            print(entry)
            print('-----')

def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

def main(p4info_file_path, bmv2_file_path):
    # 实例化一个P4runtime
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
         # 在各个主机间创建转换连接，这是由P4Runtime gRPC连接支持的。同时，转储所有P4Runtime消息发送到指定的txt文件。
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')

        #发送主仲裁更新消息，以建立此控制器
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()

        # 在交换机上配置P4程序
        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")
        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")

        # 编写各个主机间的隧道转发规则
        # 在提高题中我修改了s1与s3的连接端口为4号端口
        writeTunnelRules(p4info_helper, ingress_sw=s2,
                         dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.3.0",port=4,number=24)
        
        writeTunnelRules(p4info_helper, ingress_sw=s2,  
                         dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.0",port=3,number=24)

        writeTunnelRules(p4info_helper, ingress_sw=s2,
                         dst_eth_addr="08:00:00:00:02:22", dst_ip_addr="10.0.2.22",port=1,number=32)

        writeTunnelRules(p4info_helper, ingress_sw=s2,
                         dst_eth_addr="08:00:00:00:02:02", dst_ip_addr="10.0.2.2",port=2,number=32)

        writeTunnelRules(p4info_helper, ingress_sw=s1,  
                         dst_eth_addr="08:00:00:00:01:11", dst_ip_addr="10.0.1.11",port=1,number=32)

        writeTunnelRules(p4info_helper, ingress_sw=s1,  
                         dst_eth_addr="08:00:00:00:01:01", dst_ip_addr="10.0.1.1",port=2,number=32)

        writeTunnelRules(p4info_helper, ingress_sw=s1,
                         dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.2.0",port=3,number=24)

        writeTunnelRules(p4info_helper, ingress_sw=s1,
                         dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.3.0",port=4,number=24)

        writeTunnelRules(p4info_helper, ingress_sw=s3,  
                         dst_eth_addr="08:00:00:00:03:03", dst_ip_addr="10.0.3.3",port=1,number=32)

        writeTunnelRules(p4info_helper, ingress_sw=s3,  
                         dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.0",port=2,number=24)

        writeTunnelRules(p4info_helper, ingress_sw=s3,
                         dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.2.0",port=3,number=24)


        # 从s1、s2、s3中读取表项
        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    # 自定义命令参数。在使用命令行时，将相应的参数传进来，无参数时使用默认的文件。
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/qos.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/qos.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)
