<p align="center"><a href="https://oneprocloud.com"><img src="./docs/images/prophet-logo.png" alt="Prophet" width="300" /></a></p>
<h3 align="center">资源自动采集分析工具集，云迁移/云灾备必备的调研工具</h3>

<p align="center">
  <a href="https://shields.io/github/downloads/Cloud-Discovery/prophet/total"><img src="https://shields.io/github/downloads/Cloud-Discovery/prophet/total" alt=" release"></a>
  <a href="https://github.com/Cloud-Discovery/prophet"><img src="https://img.shields.io/github/stars/Cloud-Discovery/prophet?color=%231890FF&style=flat-square" alt="Stars"></a>
</p>

--------------------------

- [ENGLISH](https://github.com/Cloud-Discovery/prophet/blob/master/docs/README_EN.md)

## 目录

* [项目说明](#项目说明)
* [安装说明](#安装说明)
* [使用说明](#使用说明)
* [如何贡献](#如何贡献)
* [贡献者](#贡献者)
* [协议说明](#协议说明)

## 项目说明

Prophet是一个自动化采集、分析的工具集，目前支持对物理机、VMware环境的采集和分析，未来将扩展至云平台资源、存储、网络等多种资源。目前主要应用与云迁移与云灾备前期技术调研，主要对源端主机的基本情况进行采集，通过技术指标的比对，确保被调研的源端主机能够正确被工具正确迁移或灾备,同时根据数据量，预测数据传输时间。该项目目前已经在多个实际的云迁移和云灾备项目中得到验证，可以放心使用。

该项目未来发展的愿景是提供一站式调研平台，包括但不限于如下资源：各种云平台资源使用状况、文件存储、对象存储、容器平台、大数据平台、中间件、数据库等。同时也将提供蓝图画板，方便在项目前期进行方案编写使用，降低云迁移与云灾备过于冗长的前期调研周期。

目前Prophet主要有以下功能组成：

* 通过nmap指令扫描全网存活的主机，并尽量通过包信息分析主机的基本情况
* (稳定)通过VMWare API接口采集主机的详细信息，包含计算、存储和网络等与主机迁移
* (稳定)通过Ansible获取Linux主机的详细信息，包含计算、存储和网络等与主机相关信息
* (稳定)通过Windows WMI接口采集Windows主机的详细信息，包含计算、存储和网络等与主机相关信息
* (稳定)将采集后的结果以yaml格式进行打包和压缩，并进行脱敏处理（移除用户相关信息）
* (稳定)对采集后的结果进行分析，得出最终的技术调研结论

## 安装说明

推荐使用容器方式使用Prophet，减少环境依赖。

### 容器方式

目前该项目每次提交后都会自动进行构建并推送到国内容器源中，可以直接使用，首先确保本地运行环境已经安装docker环境。

* 下载prophet容器镜像

  ```
  docker pull \
    registry.cn-beijing.aliyuncs.com/oneprocloud-opensource/cloud-discovery-prophet:latest
  ```

* 运行prophet容器服务

  ```
  docker run \
    -d \
    -ti \
    --name prophet \
    registry.cn-beijing.aliyuncs.com/oneprocloud-opensource/cloud-discovery-prophet:latest
  ```

* 访问prophet容器

  容器运行后，即可访问到容器内容进行后续操作使用

  ```
  docker exec -ti prophet bash

  prophet-cli {scan,collect,report}
  ```


### 源码安装

#### 前提条件

* Python环境运行版本

  python3 以上版本，安装python3 pbr的开发包

* 依赖包安装

  * RHEL & CentOS

    提前安装配置epel仓库源，在执行安装依赖包指令，目前暂时只提供RHEL&CentOS版本，后续持续更新

    ```
    yum install -y epel-release
    cd prophet/
    yum install -y nmap sshpass
      ```

#### 源码下载安装

```
git clone https://github.com/Cloud-Discovery/prophet

cd prophet
virtualenv venv
source venv/bin/activate

pip install -U pip
pip install -r requirements.txt
pip install .

# 安装远程 windows 执行所需wmi模块
yum install -y ./tools/wmi-1.3.14-4.el7.art.x86_64.rpm
```

## 使用说明

### 基本使用流程

1. 扫描指定的IP地址段
2. 在扫描结果的csv中，填写需要获取详情的主机鉴权信息
3. 批量采集
4. 分析, 得到结果

### (稳定)功能一：扫描全网运行的实例

#### 功能说明

通过网络扫描发现某一网段内存活的主机，并进行记录，可以作为后续更详细信息采集的输入。扫描完成后，将自动在指定路径下生成scan_results.csv文件，用于存储信息。

***** 注意：为了防止对生产环境造成较大压力，扫描时采用单进程方式，所以扫描进度较慢，经过测算扫描一个子网掩码为24的子网所需要30分钟左右的时间。**

```
usage: prophet-cli scan [-h] --host HOST [--arg ARG] --output-path OUTPUT_PATH
                        [--report-name REPORT_NAME]

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           Input host, example: 192.168.10.0/24, 192.168.10.1-2
  --arg ARG             Arguments for nmap, for more detailed, please check
                        nmap document
  --output-path OUTPUT_PATH
                        Generate initial host report path
  --report-name REPORT_NAME
                        Scan report csv name
```

#### 示例一: 获取子网主机

扫描192.168.10.0/24所有存活主机信息，并将csv文件生成在/tmp目录中。

```
prophet-cli scan --host 192.168.10.0/24 --output-path /tmp/
```

#### 示例二: 获取指定IP网段主机

扫描192.168.10.2-192.168.10.50所有存活主机信息，并将csv文件生成在/tmp目录中。

```
prophet-cli scan --host 192.168.10.2-50 --output-path /tmp/
```

#### csv结构说明

| 字段名称         | 字段说明                                                        |
|--------------|-------------------------------------------------------------|
| hostname     | 主机名，可以为空                                                    |
| ip           | 用户IP地址，必须                                                   |
| username     | 用户名，如果为VMware，则为ESXi或者vCenter的用户名                           |
| password     | 密码，如果为VMware，则为ESXi或者vCenter的用户名                              |
| ssh_port     | Linux，该字段为ssh端口VMware ESXi或vCenter则为连接端口，默认为443Windows则默认为空 |
| key_path     | 如果为密钥登陆，需要指定密钥的绝对路径，否则为空                                    |
| mac          | 主机MAC地址，可以为空                                                |
| vendor       | 生产厂商，可以为空，如果是VMware运行的虚拟机则为VMware                           |
| check_status | 是否需要采集详细信息, 如果需要则设置为check，否则工具将自动跳过                  |
| os           | 操作系统类型，目前支持的类型为：Linux/Windows/VMware，大小写敏感                  |
| version      | 操作系统的版本，可以为空                                                |
| tcp_ports    | 对外开放的端口，可以为空                                                |
| do_status    | 详细信息采集状态，表示是否完成采集或者失败，默认为空                                  |

### (稳定)功能二：详细信息采集

#### 功能说明

用户在模板填入鉴权信息后，进行进一步详细扫描。

注意：

* 如果希望扫描的主机，则需要将check_status修改为check，否则不进行检查
* 如果是VMware的虚拟机，则只会通过所在的ESXi主机进行扫描
* 如果是Windows主机，需要Administrator用户进行扫描
* 采集主机如果成功，则再次运行脚本时不会再进行采集，除非用户指定force-check参数
* 采集失败的主机在下一次采集时，会重新采集
* 最终生产的压缩包，一切与用户鉴权相关的敏感信息都已经被移除
* (稳定)目前VMware采集部分是稳定的
* (测试)目前Linux和Windows采集部分仍然是测试版本

```
usage: prophet-cli collect [-h] --host-file HOST_FILE --output-path
                           OUTPUT_PATH [-f] [--package-name PACKAGE_NAME]

optional arguments:
  -h, --help            show this help message and exit
  --host-file HOST_FILE
                        Host file which generated by network scan
  --output-path OUTPUT_PATH
                        Output path for batch collection
  -f, --force-check     Force check all hosts
  --package-name PACKAGE_NAME
                        Prefix name for host collection package
```

#### 示例：执行采集

首先需要在生成的scan_results.csv中更新要采集主机的鉴权信息，在项目中的examples路径包含(scan_results.csv)[https://github.com/Cloud-Discovery/prophet/blob/master/examples/scan_results.csv]样例。

|hostname|ip            |username                   |password             |ssh_port|key_path|mac              |vendor|check_status|os     |version                                   |tcp_ports                                                                            |do_status|
|--------|--------------|---------------------------|---------------------|--------|--------|-----------------|------|------------|-------|------------------------------------------|-------------------------------------------------------------------------------------|---------|
|        |192.168.10.2  |administrator@vsphere.local|your_vcenter_password|        |        |00:50:56:9f:03:f0|      |check       |Windows|Microsoft Windows 7 or Windows Server 2012|80,88,135,139,389,443,445,514,636,2020,3389,8088,9009,9090                           |         |
|        |192.168.10.6  |root                       |your_esxi_password   |443     |        |0c:c4:7a:e5:5d:20|      |check       |VMware |VMware ESXi Server 4.1                    |22,80,427,443,902,5988,5989,8000,8080,8100,8300                                      |         |
|        |192.168.10.185|Administrator              |your_windows_password|        |        |00:50:56:9a:6d:2e|      |check       |Windows|Microsoft Windows Server 2003 SP1 or SP2  |135,139,445,1028,3389                                                                |         |
|        |192.168.10.201|root                       |your_linux_password  |22      |        |ac:1f:6b:27:7f:e4|      |check       |Linux  |Linux 2.6.32 - 3.9                        |22,80,3306,4567,5000,5900,5901,5902,5903,5904,5906,5907,5910,5911,5915,8022,8080,9100|         |


```
prophet-cli collect --host-file /tmp/scan_hosts.csv --output-path /tmp
```

#### 采集结果说明

采集目录结构

```
hosts_collection
|-- LINUX -> Linux主机采集信息
|-- VMWARE -> VMWare主机采集信息
`-- WINDOWS -> Windows主机采集信息
|-- prophet.log -> 采集过程中的日志，便于对于未知场景分析
|-- scan_hosts.csv -> 采集的主机文件，含开放端口信息
```

另外在输出目录中会生成hosts_collection_xxxxxxx.zip文件，该文件为最终用于分析的压缩文件。

### (重构中)功能三: 分析并输出报告

#### 功能说明

将采集后的结果进行分析，并输出最终的可迁移性报告，该部分可以根据需求扩展。

```
usage: prophet-cli report [-h] --package-file PACKAGE_FILE --output-path
                          OUTPUT_PATH [--report-name REPORT_NAME] [--clean]

optional arguments:
  -h, --help            show this help message and exit
  --package-file PACKAGE_FILE
                        Investigate package file which is genreated by
                        prophet-collect
  --output-path OUTPUT_PATH
                        Generate report path
  --report-name REPORT_NAME
                        Generate report name
  --clean               Clean temp work dir or not, by default is not
```

#### 示例：分析并输出报告

```
prophet-cli -d -v report --package-file /tmp/hosts_collection_20211215202459.zip --output-path /tmp
```

#### 示例：分析报告

|平台类型    |主机名                  |VMware主机名|IP                      |Mac              |操作系统类型                            |操作系统版本                            |操作系统位数|操作系统内核版本             |启动方式|CPU                                      |CPU核数|内存             |总内存(GB) |剩余内存(GB)|磁盘数量|磁盘总容量(GB)  |磁盘信息                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |分区信息                                                                                                                             |网卡数量|网卡信息                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |虚拟化类型            |虚拟化版本                          |ESXi服务器              |
|--------|---------------------|---------|------------------------|-----------------|----------------------------------|----------------------------------|------|---------------------|----|-----------------------------------------|-----|---------------|--------|--------|----|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|----|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------|-------------------------------|---------------------|
|Physical|compute201           |         |192.168.10.201          |ac:1f:6b:27:7f:e4|CentOS                            |7.5.1804                          |x86_64|3.10.0-862.el7.x86_64|bios|Intel(R) Xeon(R) CPU E5-2630 v4 @ 2.20GHz|40   |               |62.65   |5.35    |7   |5467004.78 |sda&#124;56266.78&#124;ATA&#124;SuperMicro SSD sdb&#124;213212.97&#124;ATA&#124;INTEL SSDSC2BB24 sdc&#124;1039505.00&#124;SEAGATE&#124;ST1200MM0007 sdd&#124;1039505.00&#124;SEAGATE&#124;ST1200MM0007 sde&#124;1039505.00&#124;SEAGATE&#124;ST1200MM0007 sdf&#124;1039505.00&#124;TOSHIBA&#124;AL15SEB120NY sdg&#124;1039505.00&#124;TOSHIBA&#124;AL15SEB120NY                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |/dev/sda2&#124;62245572608&#124;58963365888&#124;0.95&#124;xfs /dev/sda1&#124;1063256064&#124;922746880&#124;0.87&#124;xfs /dev/sdc1&#124;1199655976960&#124;1141407465472&#124;0.95&#124;xfs|4   |eno1&#124;0c:c4:7a:a5:29:3a&#124;True&#124;1500&#124;10000&#124;10.0.100.201&#124;255.255.255.0&#124;10.0.100.0&#124;10.0.100.255&#124;fe80::ec4:7aff:fea5:293a ens2f3&#124;ac:1f:6b:27:7f:e7&#124;True&#124;1500&#124;1000&#124;None&#124;None&#124;None&#124;None&#124;fe80::ae1f:6bff:fe27:7fe7 ens2f0&#124;ac:1f:6b:27:7f:e4&#124;True&#124;1500&#124;1000&#124;192.168.10.201&#124;255.255.255.0&#124;192.168.10.0&#124;192.168.10.255&#124;192.168.10.1&#124;fe80::ae1f:6bff:fe27:7fe4 ens2f1&#124;ac:1f:6b:27:7f:e5&#124;True&#124;1500&#124;1000&#124;172.16.100.201&#124;255.255.255.0&#124;172.16.100.0&#124;172.16.100.255&#124;fe80::ae1f:6bff:fe27:7fe5|                 |                               |                     |
|Physical|compute202           |         |192.168.10.202          |0c:c4:7a:e5:5c:f8|CentOS                            |7.5.1804                          |x86_64|3.10.0-862.el7.x86_64|bios|Intel(R) Xeon(R) CPU E5-2630 v4 @ 2.20GHz|40   |               |62.65   |13.27   |7   |5467004.78 |sda&#124;56266.78&#124;ATA&#124;SuperMicro SSD sdb&#124;213212.97&#124;ATA&#124;INTEL SSDSC2BB24 sdc&#124;1039505.00&#124;SEAGATE&#124;ST1200MM0007 sdd&#124;1039505.00&#124;SEAGATE&#124;ST1200MM0007 sde&#124;1039505.00&#124;SEAGATE&#124;ST1200MM0007 sdf&#124;1039505.00&#124;TOSHIBA&#124;AL15SEB120NY sdg&#124;1039505.00&#124;TOSHIBA&#124;AL15SEB120NY                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |/dev/sda2&#124;62245572608&#124;52926242816&#124;0.85&#124;xfs /dev/sda1&#124;1063256064&#124;922746880&#124;0.87&#124;xfs                                               |4   |eno1&#124;0c:c4:7a:a5:2e:d0&#124;True&#124;1500&#124;10000&#124;10.0.100.202&#124;255.255.255.0&#124;10.0.100.0&#124;10.0.100.255&#124;fe80::ec4:7aff:fea5:2ed0 ens2f3&#124;0c:c4:7a:e5:5c:fb&#124;True&#124;1500&#124;1000&#124;None&#124;None&#124;None&#124;None&#124;fe80::ec4:7aff:fee5:5cfb ens2f0&#124;0c:c4:7a:e5:5c:f8&#124;True&#124;1500&#124;1000&#124;192.168.10.202&#124;255.255.255.0&#124;192.168.10.0&#124;192.168.10.255&#124;192.168.10.1&#124;fe80::ec4:7aff:fee5:5cf8 ens2f1&#124;0c:c4:7a:e5:5c:f9&#124;True&#124;1500&#124;1000&#124;172.16.100.202&#124;255.255.255.0&#124;172.16.100.0&#124;172.16.100.255&#124;fe80::ec4:7aff:fee5:5cf9   |                 |                               |                     |
|VMware  |node01               |         |                        |00:50:56:9a:49:b7|CentOS 4/5/6/7                    |CentOS 4/5/6/7                    |64-bit|                     |efi |Intel(R) Xeon(R) CPU E5-2680 0 @ 2.70GHz |4    |               |8192.00 |        |1   |51200.00   |[10.3-4T-5] centos7.4_node_139/centos7.4_node_139.vmdk&#124;51200.00                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |                                                                                                                                 |1   |VM Network&#124;00:50:56:9a:49:b7                                                                                                                                                                                                                                                                                                                                                                                                                                               |VMware ESX Server|VMware ESXi 6.0.0 build-2715440|192.168.10.3         |
|VMware  |master03             |         |                        |00:50:56:9a:63:a0|CentOS 4/5/6/7                    |CentOS 4/5/6/7                    |64-bit|                     |efi |Intel(R) Xeon(R) CPU E5-2680 0 @ 2.70GHz |4    |               |4096.00 |        |1   |51200.00   |[10.3-4T-5] centos7.2_132/centos7.2_132.vmdk&#124;51200.00                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |                                                                                                                                 |1   |VM Network&#124;00:50:56:9a:63:a0                                                                                                                                                                                                                                                                                                                                                                                                                                               |VMware ESX Server|VMware ESXi 6.0.0 build-2715440|192.168.10.3         |
|VMware  |master02             |         |                        |00:50:56:9a:06:ad|CentOS 4/5/6/7                    |CentOS 4/5/6/7                    |64-bit|                     |efi |Intel(R) Xeon(R) CPU E5-2680 0 @ 2.70GHz |4    |               |4096.00 |        |1   |51200.00   |[10.3-4T-5] centos7.3_131/centos7.3_131.vmdk&#124;51200.00                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |                                                                                                                                 |1   |VM Network&#124;00:50:56:9a:06:ad                                                                                                                                                                                                                                                                                                                                                                                                                                               |VMware ESX Server|VMware ESXi 6.0.0 build-2715440|192.168.10.3         |
|Physical|COMPUTER-PC          |         |192.168.10.62           |00:0c:29:9a:59:73|Microsoft Windows 7 旗舰版           |Microsoft Windows 7 旗舰版           |64-bit|6.1.7600             |bios|Intel(R) Xeon(R) CPU E5-2680 0 @ 2.70GHz |4    |Physical Memory|8191.55 |4.83    |2   |255996.72  |0&#124;51199.34&#124;VMware Virtual disk SCSI Disk Device&#124;VMware Virtual disk SCSI Disk Device 1&#124;204797.37&#124;VMware Virtual disk SCSI Disk Device&#124;VMware Virtual disk SCSI Disk Device                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |C:&#124;53580132352&#124;4455071744&#124;0.08&#124;NTFS D:&#124;109887614976&#124;109790175232&#124;1.0&#124;NTFS E:&#124;104857595904&#124;104760311808&#124;1.0&#124;NTFS                  |1   |[00000007] Intel(R) PRO/1000 MT Network Connection&#124;00:0c:29:9a:59:73&#124;192.168.10.1&#124;192.168.10.62&#124;255.255.255.0                                                                                                                                                                                                                                                                                                                                                              |                 |                               |                     |

### (稳定)功能四：云平台产品单价采集

#### 功能说明

用户填入鉴权信息（AK/SK）后，进行公网对应云平台产品单价采集。采集完成后，将产品单价信息存储在对应json文件内。

云平台支持情况：
* 华为云中国站：huawei_cn
* 华为云国际站：huawei_intl

注意：
* 华为云采集资源OpenAPI接口最多支持 10次/秒 调用


```
usage: prophet-cli price [-h] --cloud CLOUD --ak AK --sk SK --output-path
                         OUTPUT_PATH

optional arguments:
  -h, --help            show this help message and exit
  --cloud CLOUD         Cloud platform acronyms
  --ak AK               Cloud authentication access key id
  --sk SK               Cloud authentication access key id
  --output-path OUTPUT_PATH
                        Generate report path

```

#### 示例：执行采集

采集华为云国际站产品单价，并将json文件打包为zip存储在/tmp目录中。

```
prophet-cli price --cloud huawei_intl --ak xxx --sk yyy --output-path /tmp/
```

#### 采集结果说明

采集目录结构

```
huawei_intl/
│
├── regions/ -> 云平台多个资源池产品单价信息
│   ├── af-south-1.json -> 云平台资源池内产品单价信息
│   └── cn-south-1.json
│
├── region.json -> 云平台资源池信息
```

另外在输出目录中会生成huawei_intl_xxxxxxx.zip文件（根据输入的云平台简称），该文件为最终用于分析的压缩文件。



## 如何贡献

TODO: 开发者文档待完成

## 协议说明

本项目采用[木兰公共许可证，第2版](http://license.coscl.org.cn/MulanPubL-2.0)

## 贡献者

感谢以下贡献者为本项目做出的贡献

<a href="https://github.com/Cloud-Discovery/prophet/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Cloud-Discovery/prophet" />
</a>
