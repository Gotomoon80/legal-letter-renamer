@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo Final Encoding Fixed File Rename Tool (Descending Order)
echo ======================================================

:: 内置千字文内容（分段存储避免命令行限制）
set "QZW1=天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏闰余成岁律吕调阳云腾致雨露结为霜金生丽水玉出昆冈剑号巨阙珠称夜光果珍李柰菜重芥姜海咸河淡鳞潜羽翔龙师火帝鸟官人皇始制文字乃服衣裳推位让国有虞陶唐吊民伐罪周发殷汤坐朝问道垂拱平章爱育黎首臣伏戎羌遐迩一体率宾归王鸣凤在竹白驹食场化被草木赖及万方盖此身发四大五常恭惟鞠养岂敢毁伤女慕贞洁男效才良知过必改得能莫忘罔谈彼短靡恃己长信使可覆器欲难量墨悲丝染诗赞羔羊景行维贤克念作圣德建名立形端表正空谷传声虚堂习听祸因恶积福缘善庆尺璧非宝寸阴是竞资父事君曰严与敬孝当竭力忠则尽命临深履薄夙兴温凊似兰斯馨如松之盛川流不息渊澄取映容止若思言辞安定笃初诚美慎终宜令荣业所基籍甚无竟学优登仕摄职从政存以甘棠去而益咏乐殊贵贱礼别尊卑上和下睦夫唱妇随外受傅训入奉母仪诸姑伯叔犹子比儿孔怀兄弟同气连枝交友投分切磨箴规仁慈隐恻造次弗离节义廉退颠沛匪亏性静情逸心动神疲守真志满逐物意移坚持雅操好爵自縻都邑华夏东西二京背邙面洛浮渭据泾宫殿盘郁楼观飞惊图写禽兽画彩仙灵丙舍旁启甲帐对楹肆筵设席鼓瑟吹笙升阶纳陛弁转疑星右通广内左达承明既集坟典亦聚群英杜稿钟隶漆书壁经府罗将相路侠槐卿户封八县家给千兵高冠陪辇驱毂振缨世禄侈富车驾肥轻策功茂实勒碑刻铭磻溪伊尹佐时阿衡奄宅曲阜微旦孰营桓公匡合济弱扶倾绮回汉惠说感武丁俊乂密勿多士寔宁晋楚更霸赵魏困横假途灭虢践土会盟何遵约法韩弊烦刑起翦颇牧用军最精宣威沙漠驰誉丹青九州禹迹百郡秦并岳宗泰岱禅主云亭雁门紫塞鸡田赤城昆池碣石钜野洞庭旷远绵邈岩岫杳冥治本于农务兹稼穑俶载南亩我艺黍稷税熟贡新劝赏黜陟孟轲敦素史鱼秉直庶几中庸劳谦谨敕聆音察理鉴貌辨色贻厥嘉猷勉其祗植省躬讥诫宠增抗极殆辱近耻林皋幸即两疏见机解组谁逼索居闲处沉默寂寥求古寻论散虑逍遥欣奏累遣戚谢欢招渠荷的历园莽抽条枇杷晚翠梧桐早凋陈根委翳落叶飘摇游鹍独运凌摩绛霄耽读玩市寓目囊箱易輶攸畏属耳垣墙具膳餐饭适口充肠饱饫烹宰饥厌糟糠亲戚故旧老少异粮妾御绩纺侍巾帷房纨扇圆絜银烛炜煌昼眠夕寐蓝笋象床弦歌酒宴接杯举觞矫手顿足悦豫且康嫡后嗣续祭祀烝尝稽颡再拜悚惧恐惶笺牒简要顾答审详骸垢想浴执热愿凉驴骡犊特骇跃超骧诛斩贼盗捕获叛亡布射僚丸嵇琴阮啸恬笔伦纸钧巧任钓释纷利俗并皆佳妙毛施淑姿工颦妍笑年矢每催曦晖朗曜璇玑悬斡晦魄环照指薪修祜永绥吉劭矩步引领俯仰廊庙束带矜庄徘徊瞻眺孤陋寡闻愚蒙等诮谓语助者焉哉乎也"

:: 显示前几个字符以验证读取成功
echo Successfully loaded qianziwen dictionary

:: 初始化计数器和统计变量
set success_count=0
set error_count=0

echo.
echo Collecting files...
echo.

:: 创建临时文件列表
set temp_list=%temp%\file_list_%random%.txt
if exist "%temp_list%" del "%temp_list%"

:: 收集所有要处理的文件（按大小排序，降序）
for /f "tokens=*" %%f in ('dir /b /a-d /o-s-') do (
    set "process_file=1"
    
    :: 排除所有批处理文件和PowerShell脚本文件
    if /i "%%~xf"==".bat" set process_file=0
    if /i "%%~xf"==".ps1" set process_file=0
    
    :: 排除特定的重要文件
    if /i "%%~nxf"=="final_encoding_fixed_rename_asc.bat" set process_file=0
    if /i "%%~nxf"=="final_encoding_fixed_rename_desc.bat" set process_file=0
    
    if !process_file! equ 1 (
        echo "%%f" >> "%temp_list%"
    )
)

:: 计算文件总数
set file_count=0
for /f %%i in ('type "%temp_list%" 2^>nul') do set /a file_count+=1

echo Found %file_count% files to process
echo.

:: 初始化计数器（从文件总数开始倒数，实现降序编号）
set counter=%file_count%

echo Processing files...
echo.

:: 处理文件列表（按降序处理，编号从大到小）
if exist "%temp_list%" (
    for /f "delims=" %%g in ('type "%temp_list%"') do (
        :: 去除引号
        set "filename=%%g"
        set "filename=!filename:"=!"
        
        echo Processing: "!filename!"
        
        :: 检查文件是否存在
        if exist "!filename!" (
            :: 获取文件扩展名
            for %%x in ("!filename!") do set "file_ext=%%~xx"
            
            :: 确保计数器是正数
            if !counter! lss 1 set counter=1
            
            :: 生成4位数字编号
            set "num=000!counter!"
            set "num=!num:~-4!"
            
            :: 计算千字文位置（确保非负数）
            set /a "index=!counter! - 1"
            if !index! lss 0 set index=0
            
            set /a "pos1=!index! * 2"
            set /a "pos2=!index! * 2 + 1"
            
            echo Counter: !counter!, Positions: !pos1! and !pos2!
            
            set "char1="
            set "char2="
            set "suffix="
            
            :: 获取千字文字符（使用更可靠的方法）
            for /f "delims=" %%c in ('powershell -command "& {try { $chars = '%QZW1%'; if ($chars.Length -gt !pos1! -and $chars.Length -gt !pos2!) { $c1 = $chars.Substring(!pos1!, 1); $c2 = $chars.Substring(!pos2!, 1); Write-Output \"$c1`n$c2\" } else { Write-Output \"X`nX\" } } catch { Write-Output \"X`nX\" }}" 2^>nul') do (
                if not defined char1 (
                    set "char1=%%c"
                ) else (
                    set "char2=%%c"
                )
            )
            
            :: 设置后缀
            if defined char1 if defined char2 (
                set "suffix=!char1!!char2!"
            ) else (
                set "suffix=XX"
            )
            
            echo Got suffix: "!suffix!"
            
            :: 新文件名：数字编号+千字文后缀+原扩展名
            set "new_name=!num!!suffix!!file_ext!"
            
            :: 清理文件名中的特殊字符
            set "new_name=!new_name:"=!"
            
            echo New name: "!new_name!"
            
            :: 第一步：重命名为临时名称(tbd)
            set "temp_name=tbd_!num!!file_ext!"
            echo Step 1: Renaming "!filename!" to temporary name "!temp_name!"
            ren "!filename!" "!temp_name!" 2>nul
            
            if errorlevel 1 (
                echo Error: Failed to rename "!filename!" to "!temp_name!"
                set /a error_count+=1
            ) else (
                :: 第二步：重命名为最终名称
                echo Step 2: Renaming "!temp_name!" to "!new_name!"
                ren "!temp_name!" "!new_name!" 2>nul
                
                if errorlevel 1 (
                    echo Error: Failed to rename "!temp_name!" to "!new_name!"
                    set /a error_count+=1
                ) else (
                    echo Success: "!filename!" -^> "!new_name!"
                    set /a success_count+=1
                )
            )
        ) else (
            echo Error: File "!filename!" does not exist
            set /a error_count+=1
        )
        
        set /a counter-=1
        echo.
    )
    
    :: 删除临时文件
    if exist "%temp_list%" del "%temp_list%"
)

echo.
echo Process completed!
echo Successfully renamed: %success_count% files
echo Failed: %error_count% files
echo.
echo Press any key to exit...
pause >nul