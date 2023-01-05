#SingleInstance, Force
SendMode Input
SetWorkingDir, %A_ScriptDir%
actualstart:

gotnums = 0

IfNotExist, ../settings.ini
{
    MsgBox, settings.ini file not found. Creating file...
    FileAppend, , ../settings.ini
    IniWrite, % "1", ../settings.ini, SPIKER, FirstTimeLaunch
    log.addLogEntry("Created settings.ini")
}


IniRead, mutehotkey, ../settings.ini, SPIKER, mutehotkey
IniRead, FirstTimeLaunch, ../settings.ini, SPIKER, FirstTimeLaunch
if (FirstTimeLaunch != 0)
    Tutorial()

OnMessage(0x202, "ClickEvent")
Gui, Add, Tab3,, Input|How to use

Gui, Add, Text, x22 y+10p, Ship:
Gui, add, Radio,x+5p vship3 group, Sloop
Gui, add, Radio,x+5p vship2 Checked, Brigantine
Gui, add, Radio,x+5p vship1, Galleon
Gui, Add, Checkbox,x22 y+10p vcaptaincy, Captaincy spike (will default to last used ship)
Gui, Add, Checkbox,x22 y+10p vportspike, Port spike (Will restart the script with Admin privileges)
Gui, Add, CheckBox,x22 y+10p vmutedc, Mute discord when on set sail screen.
Gui, Add, Text,x22 y+10p, Discord mute hotkey:
Gui, Add, Hotkey,x125 y127 vmutehotkey, %mutehotkey%

Gui, Tab, 2
Gui, Add, Text,, Select ship type.`n`nIf you select captaincy you will get the most recently used ship.`n`nIf you select portspike it will automatically post the port number.`n`nIf you select mute discord when on set sail screen it will automatically`nmute discord when you are on the set sail screen.
Gui, Tab
Gui, Add, Button, x10, Continue
Gui, Add, Button,x+10p, Redo initial setup
Gui, show

Return
ButtonContinue:
Gui, Submit
Gui, Destroy

IniWrite, %mutehotkey%, ../settings.ini, SPIKER, mutehotkey

if (ship1 == 0 && ship2 == 0 && ship3 == 0 && captaincy == 0)
{
    MsgBox, At least one option must be selected
    goto, actualstart
}

if mutedc
{
    OutputDebug, %mutehotkey%
    if (mutehotkey == "")
    {    
        MsgBox, Mute hotkey can not be None...
        Goto, actualstart
    }
}

if portspike
{
    full_command_line := DllCall("GetCommandLine", "str")
    if not (A_IsAdmin or RegExMatch(full_command_line, " /restart(?!\S)"))
    {
        MsgBox, Restarting script to run with admin privileges...
        try ; leads to having the script re-launching itself as administrator
        {
            if A_IsCompiled
                Run *RunAs "%A_ScriptFullPath%" /restart
            else
                Run *RunAs "%A_AhkPath%" /restart "%A_ScriptFullPath%"
        }
        ExitApp
    }
}

start:

IniRead, mainColor, ../settings.ini, SPIKER, mainColor
IniRead, mainCoords, ../settings.ini, SPIKER, mainCoords
IniRead, playColor, ../settings.ini, SPIKER, playColor
IniRead, playCoords, ../settings.ini, SPIKER, playCoords
IniRead, experienceColor, ../settings.ini, SPIKER, experienceColor
IniRead, experienceCoords, ../settings.ini, SPIKER, experienceCoords
IniRead, selectShipColor, ../settings.ini, SPIKER, selectShipColor
IniRead, selectShipCoords, ../settings.ini, SPIKER, selectShipCoords
IniRead, confirmColor, ../settings.ini, SPIKER, confirmColor
IniRead, confirmCoords, ../settings.ini, SPIKER, confirmCoords
IniRead, setSailColor, ../settings.ini, SPIKER, setSailColor
IniRead, setSailCoords, ../settings.ini, SPIKER, setSailCoords
IniRead, loadingColor, ../settings.ini, SPIKER, loadingColor
IniRead, loadingCoords, ../settings.ini, SPIKER, loadingCoords
IniRead, errorColor, ../settings.ini, SPIKER, errorColor
IniRead, errorCoords, ../settings.ini, SPIKER, errorCoords

z = 0
loop, parse, mainCoords, `,
{
    if ( z == 0 )
    {
        mainCoordsX := A_LoopField
        z++
    } Else
        mainCoordsY := A_LoopField
}
OutputDebug, %mainCoordsX% %mainCoordsY%

z = 0
loop, parse, playCoords, `,
{
    if ( z == 0 )
    {
        playCoordsX := A_LoopField
        z++
    } Else
        playCoordsY := A_LoopField
}
OutputDebug, %playCoordsX% %playCoordsY%

z = 0
loop, parse, experienceCoords, `,
{
    if ( z == 0 )
    {
        experienceCoordsX := A_LoopField
        z++
    } Else
        experienceCoordsY := A_LoopField
}
OutputDebug, %experienceCoordsX% %experienceCoordsY%

z = 0
loop, parse, selectShipCoords, `,
{
    if ( z == 0 )
    {
        selectShipCoordsX := A_LoopField
        z++
    } Else
        selectShipCoordsY := A_LoopField
}
OutputDebug, %selectShipCoordsX% %selectShipCoordsY%

z = 0
loop, parse, confirmCoords, `,
{
    if ( z == 0 )
    {
        confirmCoordsX := A_LoopField
        z++
    } Else
        confirmCoordsY := A_LoopField
}
OutputDebug, %confirmCoordsX% %confirmCoordsY%

z = 0
loop, parse, setSailCoords, `,
{
    if ( z == 0 )
    {
        setSailCoordsX := A_LoopField
        z++
    } Else
        setSailCoordsY := A_LoopField
}
OutputDebug, %setSailCoordsX% %setSailCoordsY%

z = 0
loop, parse, loadingCoords, `,
{
    if ( z == 0 )
    {
        loadingCoordsX := A_LoopField
        z++
    } Else
        loadingCoordsY := A_LoopField
}
OutputDebug, %loadingCoordsX% %loadingCoordsY%

z = 0
loop, parse, errorCoords, `,
{
    if ( z == 0 )
    {
        errorCoordsX := A_LoopField
        z++
    } Else
        errorCoordsY := A_LoopField
}
OutputDebug, %errorCoordsX% %errorCoordsY%

if not WinExist("Sea of Thieves")
{
    Sleep, 1000
    Send, {LWinDown}{LWinUp}
    Sleep, 1000
    Send, Sea of thieves
    Sleep, 1000
    Send, {Enter}
    SOTneedsopen = 1
}
else
{
    WinActivate, Sea of Thieves
    Sleep, 1000
}


WinWaitActive, Sea of Thieves
Sleep, 2000
WinGet, iswinmax, MinMax, Sea of Thieves
WinRestore, Sea of Thieves
OutputDebug, %iswinmax%
WinGetPos, X, Y, W, H, Sea of Thieves
WinActivate, Sea of Thieves

if (X == 0 and iswinmax == 0)
{
    Sleep, 1500
    Send, !{Enter}
} else if (X == 0 and iswinmax == 1)
{
    Sleep, 1500
    Send, !{Enter}
}
OutputDebug, % X iswinmax

; Move sot window

Sleep, 500
WinMove, Sea of Thieves,, 300, 150, 1200, 820
WinActivate, Sea of Thieves

; Setup port spike

if portspike
{
    OutputDebug, portspike
    if not WinExist("LiveTcpUdpWatch")
    {
        Sleep, 1000
        Send, {LWinDown}{LWinUp}
        Sleep, 1000
        Send, LiveTcpUdpWatch.exe
        Sleep, 1000
        Send, {BackSpace}
        Sleep, 500
        Send, {Enter}
    }
    else
    {
        WinActivate, LiveTcpUdpWatch
        Sleep, 1000
    }
    WinWaitActive, LiveTcpUdpWatch
    Sleep, 500
    Send, ^x
    Sleep, 500
    OutputDebug, set up livetcpudpwatch
    sleep, 500
}

WinActivate, Sea of Thieves

; Determine starting position
if (!SOTneedsopen)
{
    Loop,
    {
    OutputDebug, Restarted loop
    WinActivate, Sea of Thieves
    PixelGetColor, RGBmainScreen, mainCoordsX, mainCoordsY, RGB
    PixelGetColor, RGBplayScreen, playCoordsX, playCoordsY, RGB
    PixelGetColor, errorScreen, errorCoordsX, errorCoordsY, RGB
    PixelGetColor, experienceScreen, experienceCoordsX, experienceCoordsY, RGB
    PixelGetColor, shipSelectScreen, selectShipCoordsX, selectShipCoordsY, RGB
    PixelGetColor, confirmScreen, confirmCoordsX, confirmCoordsY, RGB
    PixelGetColor, setSailScreen, setSailCoordsX, setSailCoordsY, RGB

    OutputDebug, % RGBmainScreen
    OutputDebug, % RGBplayScreen
    OutputDebug, % errorScreen
    OutputDebug, % experienceScreen
    OutputDebug, % shipSelectScreen
    OutputDebug, % confirmScreen
    OutputDebug, % setSailScreen

    if (RGBmainScreen == mainColor)
        Goto, main
    else if (RGBplayScreen == playColor)
        Goto, play
    else if (errorScreen == errorColor)
        Goto, play
    else if (experienceScreen == experienceColor)
        Goto, experience
    else if (shipSelectScreen == selectShipColor)
        Goto, select_ship
    else if (confirmScreen == confirmColor)
        Goto, confirm
    else if (setSailScreen == setSailColor)
        Goto, set_sail
    }
}

; Start of script

main:
RGBmain = 0
error = 0
loop,
{
WinActivate, Sea of Thieves
if (RGBmain != mainColor)
{
    Sleep, 50
    Send, {Up}
    PixelGetColor, RGBmain, mainCoordsX, mainCoordsY, RGB
    OutputDebug, % RGBmain
} else if (RGBmain == mainColor)
{
    Send, {Enter}
    break
}
}
OutputDebug, Got past main screen

play:
RGBmain = 0
loop,
{
WinActivate, Sea of Thieves
if (RGBmain != playColor)
{
    Sleep, 50
    PixelGetColor, RGBmain, playCoordsX, playCoordsY, RGB
    OutputDebug, % RGBmain
} else if (RGBmain == playColor)
{
    Send, {Enter}
    break
}
PixelGetColor, error, errorCoordsX, errorCoordsY, RGB
if (error == errorColor)
{
    OutputDebug, Received and circumvented error message
    Send, {Esc}
}
}
OutputDebug, Got past play screen


experience:
RGBmain = 0
loop,
{
WinActivate, Sea of Thieves
if (RGBmain != experienceColor)
{
    Sleep, 50
    PixelGetColor, RGBmain, experienceCoordsX, experienceCoordsY, RGB
    OutputDebug, % RGBmain
} else if (RGBmain == experienceColor)
{
    Send, {Right}
    Sleep, 300
    Send, {Enter}
    break
}
}
OutputDebug, Got past choose your experience screen


select_ship:
RGBmain = 0
loop,
{
WinActivate, Sea of Thieves
if (RGBmain != selectShipColor)
{
    Sleep, 50
    PixelGetColor, RGBmain, selectShipCoordsX, selectShipCoordsY, RGB
    OutputDebug, % RGBmain
} else if (RGBmain == selectShipColor)
{
    if ship1
    {
        Send, {Enter}
        Break
    }
    else if ship2
    {
        Send, {Down}
        Sleep, 150
        Send, {Enter}
        break
    }
    else if ship3
    {
        Send, {Down}
        Sleep, 150    
        Send, {Down}
        Sleep, 150
        Send, {Enter}
        break
    }
    else if captaincy
    {
        Send, {Right}
        Sleep, 150
        Send, {Enter}
        break
    }
}
}
OutputDebug, Got past select your ship screen

RGBmain = 0
loop,
{
    if captaincy
    {
        PixelGetColor, RGBmain, confirmCoordsX, confirmCoordsY, RGB
        if (RGBmain != confirmColor)
        {
            OutputDebug, Trying to get to confirm screen...
            Send, {Enter}
            Sleep, 1500
        }
        else if (RGBmain == confirmColor)
            break
    }
    else if not captaincy
        break
}

confirm:
RGBmain = 0
loop,
{
WinActivate, Sea of Thieves
OutputDebug, entered loop
if (RGBmain != confirmColor)
{
    Sleep, 50
    PixelGetColor, RGBmain, confirmCoordsX, confirmCoordsY, RGB
    OutputDebug, % RGBmain
} else if (RGBmain == confirmColor)
{
    Send, {Enter}
    break
}
}
OutputDebug, Got past confirm and assemble crew screen


set_sail:
RGBmain = 0
loop,
{
WinActivate, Sea of Thieves
if (RGBmain != setSailColor)
{
    Sleep, 50
    PixelGetColor, RGBmain, setSailCoordsX, setSailCoordsY, RGB
    OutputDebug, % RGBmain
} 
else if (RGBmain == setSailColor)
    break
}

if portspike
{
    WinActivate, LiveTcpUdpWatch
    Sleep, 500
    Send, ^x
    Sleep, 500
    WinActivate, Sea of Thieves
}

if mutedc
{
    WinActivate, ahk_exe discord.exe
    Sleep, 500
    Send, %mutehotkey%
    Sleep, 250
    WinActivate, Sea of Thieves
}

OutputDebug, Got to set sail screen
Gui,+AlwaysOnTop
Gui, Add, Text,, WAITING ON SET SAIL SCREEN. Press Enter to set sail and continue
Gui, show, NA
KeyWait, Enter, D
Keywait, Enter
Gui, Destroy
RGBmain := setSailColor
loop,
{
WinActivate, Sea of Thieves
if (RGBmain == setSailColor)
{
    Sleep, 50
    PixelGetColor, RGBmain, setSailCoordsX, setSailCoordsY, RGB
    OutputDebug, % RGBmain
} 
else if (RGBmain != setSailColor)
    break
}

RGBmain = 5
loop,
{
WinActivate, Sea of Thieves
if (RGBmain != 0x000000)
{
    Sleep, 50
    PixelGetColor, RGBmain, loadingCoordsX, loadingCoordsY, RGB
    OutputDebug, % RGBmain
} else if (RGBmain == 0x000000)
    break
}
OutputDebug, Got to loading screen

loading:
RGBmain = 0
RGBmain1 = 0
RGBmain2 = 0
RGBmain3 = 0
RGBmain4 = 0
RGBmain5 = 0
RGBmain6 = 0
RGBmain7 = 0
RGBmain8 = 0
RGBmain9 = 0
loop,
{
    WinActivate, Sea of Thieves
    Sleep, 70
    PixelGetColor, RGBmain, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain1, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain2, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain3, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain4, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain5, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain6, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain7, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain8, loadingCoordsX, loadingCoordsY, RGB
    Sleep, 70
    PixelGetColor, RGBmain9, loadingCoordsX, loadingCoordsY, RGB
    OutputDebug, % RGBmain RGBmain1 RGBmain2 RGBmain3 RGBmain4 RGBmain5 RGBmain6 RGBmain7 RGBmain8 RGBmain9
    if (RGBmain != 0x000000 && RGBmain1 != 0x000000 && RGBmain2 != 0x000000 && RGBmain3 != 0x000000 && RGBmain4 != 0x000000 && RGBmain5 != 0x000000 && RGBmain6 != 0x000000 or RGBmain7 && 0x000000 or RGBmain7 && 0x000000 or RGBmain8 && 0x000000 or RGBmain9 && 0x000000)
        goto, scuttle
    if (portspike == 1 && gotnums == 0)
    {
        Sleep, 1000
        WinActivate, LiveTcpUdpWatch
        Sleep, 250
        Send, {Down}
        Sleep, 250
        Send, ^c
        Sleep, 250
        RegExMatch(Clipboard, "\b(?:30[0-9]{3}|31000)\b", portnumbig)
        OutputDebug, %portnumbig%
        Sleep, 250
        if (portnumbig == 31000)
            portnum = 000
        else
            portnum := StrReplace(portnumbig, "30",,,1)
        Sleep, 250
        OutputDebug, %portnum%
        Sleep, 250
        gotnums = 1

        ; Activate discord

        WinActivate, ahk_exe Discord.exe
        Sleep, 250
        Send, ^k
        Sleep, 100
        Send, {#}numbers
        Sleep, 600
        Send, {enter}
        Sleep, 2000

        WinActivate, ahk_exe Discord.exe
        sleep, 150
        Send, a
        Sleep, 150
        Send, ^a{Backspace}
        Sleep, 100

        Send, %portnum%
        Sleep, 250
        Send, {Enter}
        Sleep, 250
    }
}

#q::
scuttle:
MsgBox, 4, Leave game?, Do you want to leave the game?
IfMsgBox, Yes
{
    scuttleSequence()
    gotnums = 0
    Goto, start
}
IfMsgBox, No
    MsgBox, press Windows + Q to go back to the leave game window and press Windows + X to exit the macro

return

#x::
WinMove, Sea of Thieves,, %X%, %Y%, %W%, %H%
global xx := x
global yy := y
global ww := w
global hh := h
global iswinmaximized := iswinmax
if (iswinmax == 1)
    WinMaximize, Sea of Thieves
GuiClose:
ExitApp
Return

scuttleSequence()
{
    WinActivate, Sea of Thieves
    Send, {Esc}
    Sleep, 201
    Send, {Down}
    Sleep, 136
    Send, {Down}
    Sleep, 126
    Send, {Down}
    Sleep, 112
    Send, {Down}
    Sleep, 132
    Send, {Down}
    Sleep, 182
    Send, {Down}
    Sleep, 182
    Send, {Enter}
    Sleep, 320
    Send, {Enter}
}
Return

Tutorial()
{
    MsgBox, First time launch. Please walk the macro through some steps to tell it what colors to look for...

    if not WinExist("Sea of Thieves")
    {
        Sleep, 1000
        Send, {LWinDown}{LWinUp}
        Sleep, 1000
        Send, Sea of thieves
        Sleep, 1000
        Send, {Enter}
        SOTneedsopen = 1
    }
    else
    {
        WinActivate, Sea of Thieves
        Sleep, 1000
        Send, !{F4}
        Sleep, 1000
        Send, {LWinDown}{LWinUp}
        Sleep, 1000
        Send, Sea of thieves
        Sleep, 1000
        Send, {Enter}
    }

    WinWaitActive, Sea of Thieves
    OutputDebug, window found
    Sleep, 5000
    WinGet, iswinmax, MinMax, Sea of Thieves
    WinRestore, Sea of Thieves
    OutputDebug, %iswinmax%
    WinGetPos, X, Y, W, H, Sea of Thieves
    WinActivate, Sea of Thieves
    OutputDebug, %X%
    if (X == 0 and iswinmax == 0)
    {
        Sleep, 1500
        Send, !{Enter}
    } else if (X == 0 and iswinmax == 1)
    {
        Sleep, 1500
        Send, !{Enter}
    }
    OutputDebug, % X iswinmax

    ; Move sot window

    Sleep, 500
    WinMove, Sea of Thieves,, 300, 150, 1200, 820
    WinActivate, Sea of Thieves


    first:
    Gui,+AlwaysOnTop
    Gui, add, picture, w300 h-1, ..\images\main.png
    Gui, add, text,, Once you are on the main screen, right click on the T in Thieves
    Gui, show,NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, first
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, mainCoords
    IniWrite, %color%, ../settings.ini, SPIKER, mainColor
    Gui, Destroy


    second:
    Gui, add, picture, w300 h-1, ..\images\play.png
    Gui, add, text,, Once you are on the play screen, right click on the P in Play
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, second
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, playCoords
    IniWrite, %color%, ../settings.ini, SPIKER, playColor
    Gui, Destroy


    third:
    Gui, add, picture, w300 h-1, ..\images\experience.png
    Gui, add, text,, Once you are on the choose your experience screen, right click on the C in Experience
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, third
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, experienceCoords
    IniWrite, %color%, ../settings.ini, SPIKER, experienceColor
    Gui, Destroy


    fourth:
    Gui, add, picture, w300 h-1, ..\images\selectship.png
    Gui, add, text,, Once you are on the select your ship screen, right click on the S in Ship
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, fourth
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, selectShipCoords
    IniWrite, %color%, ../settings.ini, SPIKER, selectShipColor
    Gui, Destroy


    fifth:
    Gui, add, picture, w300 h-1, ..\images\confirm.png
    Gui, add, text,, Once you are on the confirm and assemble crew screen, right click on the S in Setup
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, fifth
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, confirmCoords
    IniWrite, %color%, ../settings.ini, SPIKER, confirmColor
    Gui, Destroy


    sixth:
    Gui, add, picture, w300 h-1, ..\images\setsail.png
    Gui, add, text,, Once you are on the set sail screen, right click on the S in Sail
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, sixth
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, setSailCoords
    IniWrite, %color%, ../settings.ini, SPIKER, setSailColor
    Gui, Destroy


    seventh:
    Gui, add, picture, w300 h-1, ..\images\loading.png
    Gui, add, text,, Once you are In the loading screen, right click somewhere within the red outlined area.
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350

    RGBmain = 0
    RGBmain1 = 0
    RGBmain2 = 0
    RGBmain3 = 0
    RGBmain4 = 0
    RGBmain5 = 0
    RGBmain6 = 0
    loop,
    {
    WinActivate, Sea of Thieves
    Sleep, 75
    PixelGetColor, RGBmain, %x%, %y%, RGB
    Sleep, 75
    PixelGetColor, RGBmain1, %x%, %y%, RGB
    Sleep, 75
    PixelGetColor, RGBmain2, %x%, %y%, RGB
    Sleep, 75
    PixelGetColor, RGBmain3, %x%, %y%, RGB
    Sleep, 75
    PixelGetColor, RGBmain4, %x%, %y%, RGB
    Sleep, 75
    PixelGetColor, RGBmain5, %x%, %y%, RGB
    Sleep, 75
    PixelGetColor, RGBmain6, %x%, %y%, RGB
    OutputDebug, % RGBmain RGBmain1 RGBmain2 RGBmain3 RGBmain4 RGBmain5 RGBmain6
    if not (RGBmain == RGBmain1 && RGBmain1 == RGBmain2 && RGBmain2 == RGBmain3 && RGBmain3 == RGBmain4 && RGBmain4 == RGBmain5 && RGBmain5 == RGBmain6 && RGBmain6 == RGBmain)
        break
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, loadingCoords
    IniWrite, %color%, ../settings.ini, SPIKER, loadingColor
    Gui, Destroy

    MsgBox, Almost done. Just one more to go!
    WinActivate, Sea of Thieves
    Send, !{F4}
    Gui,+AlwaysOnTop
    Gui, Add, Text,, WAITING FOR SOT TO RELAUNCH
    Gui, show, NA
    Sleep, 10000
    Gui, Destroy
    Send, {LWinDown}{LWinUp}
    Sleep, 1000
    Send, Sea of thieves
    Sleep, 1000
    Send, {Enter}
    WinWaitActive, Sea of Thieves
    Sleep, 5000
    WinGet, iswinmax, MinMax, Sea of Thieves
    WinRestore, Sea of Thieves
    OutputDebug, %iswinmax%
    WinGetPos, X, Y, W, H, Sea of Thieves
    WinActivate, Sea of Thieves

    if (X == 0 and iswinmax == 0)
    {
        Sleep, 1500
        Send, !{Enter}
    } else if (X == 0 and iswinmax == 1)
    {
        Sleep, 1500
        Send, !{Enter}
    }
    OutputDebug, % X iswinmax

    ; Move sot window

    Sleep, 500
    WinMove, Sea of Thieves,, 300, 150, 1200, 820
    WinActivate, Sea of Thieves


    eighth:
    Gui, add, picture, w300 h-1, ..\images\error.png
    Gui, add, text,, Press Start Game. If you got an error message, right click somewhere inside the red square.`nIf you did not get an error message get into a session and Alt+F4
    Gui, show, NA x0 y0
    KeyWait, RButton, D
    MouseGetPos, x, y
    PixelGetColor, color, %x%, %y%, RGB
    KeyWait, RButton
    Sleep, 350
    PixelGetColor, 1color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 2color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 3color, %x%, %y%, RGB
    Sleep, 350
    PixelGetColor, 4color, %x%, %y%, RGB
    if not (color == 1color && 1color == 2color && 2color == 3color && 3color == 4color)
    {
        MsgBox, Detected change in colors, returning to start
        Goto, eighth
    }
    IniWrite, % x . ", " . y, ../settings.ini, SPIKER, errorCoords
    IniWrite, %color%, ../settings.ini, SPIKER, errorColor
    Gui, Destroy

    IniWrite, 0, ../settings.ini, SPIKER, FirstTimeLaunch
    MsgBox, First time setup done. Restarting script...
    Sleep, 250
    WinActivate, Sea of Thieves
    Sleep, 50
    Send, Send, !{F4}
    Sleep, 3500
}
return

ButtonRedoinitialsetup:
Gui, Destroy
Msgbox,4 ,,Are you sure that you want to redo the initial setup?
IfMsgBox, Yes
{
    IniWrite, 1, ../settings.ini, SPIKER, FirstTimeLaunch
    Goto, actualstart
}
Else
    Goto, actualstart
return

ClickEvent()
{
    GuiControlGet, BoxStatus,, captaincy
    if ( A_GuiControl == "captaincy" )
        Loop 3
        {
            GuiControl, % ( BoxStatus = 0 ? "Dis" : "En" ) "able", % "ship" a_index	; if Check2 is checked, enable, if not, disable radios
            GuiControl,, % "ship" a_index, 0					; if Check2 is unchecked, reset radios
        }
}
return