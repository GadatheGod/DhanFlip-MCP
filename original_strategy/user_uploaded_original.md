**//@version=6**

**strategy("Nifty/Sensex Flip 2026", overlay = true, max_labels_count = 500,**

**&#x20;    initial_capital = 100000,**

**&#x20;    default_qty_type = strategy.percent_of_equity,**

**&#x20;    default_qty_value = 100,**

**&#x20;    commission_type = strategy.commission.percent,**

**&#x20;    commission_value = 0.05,**

**&#x20;    slippage = 2,**

**&#x20;    calc_on_every_tick = false,**

**&#x20;    process_orders_on_close = false,**

**&#x20;    pyramiding = 0)**

**&#x20;    // Store original entry/target/SL so the EXIT alert can report them correctly**

**var float storedEntry  = na**

**var float storedTarget = na**

**var float storedSL     = na**



**// ==========================================**

**// 1. INPUT SETTINGS**

**// ==========================================**

**atrPeriod = input.int(10, "ATR Length", minval = 1, group = "SuperTrend Settings")**

**factor    = input.float(4.0, "Factor", minval = 0.01, step = 0.01, group = "SuperTrend Settings")**

**emaLength = input.int(50,  title="EMA 50 Length",  group = "Indicator Settings")**

**ema200Len = input.int(200, title="EMA 200 Length", group = "Indicator Settings")**



**enableLong  = input.bool(true, title="Enable LONG Trades",  group = "Trade Direction")**

**enableShort = input.bool(false, title="Enable SHORT Trades", group = "Trade Direction")**



**useEMA200Filter = input.bool(false, title="Use EMA 200 as Signal Filter", group = "Filters")**

**ema200NaPasses = input.bool(true, title="Treat EMA 200 as PASS while still warming up (na)", group = "Filters")**



**useVWAPAtFlip   = input.bool(true, title="Require Close vs VWAP at Flip (Primary Setup)", group = "Filters")**

**useVWAPAtBreak  = input.bool(true, title="Require Close vs VWAP at EMA50 Breakout (Extended Setup)", group = "Filters")**



**useEMA200DistFilter = input.bool(false, title="Block Signal if EMA 200 is within 2x Target of Entry", group = "Filters")**

**ema200DistMult      = input.float(2.0, title="EMA 200 Minimum Distance (x Target Points)", minval=1.0, step=0.5, group = "Filters")**

**ema200CheckRising   = input.bool(true, title="Also Block if EMA 200 is Approaching from Wrong Side", group = "Filters")**



**// ==========================================**

**// SuperTrend Proximity Filter (Directional, ATR-scaled, warm-up aware)**

**// ==========================================**

**// FIX #1, #4: uses the PREVIOUS SuperTrend line (the one we just flipped**

**//             away from) as the resistance / support reference, not the**

**//             current line. At a green flip, the current line is the NEW**

**//             support; the RESISTANCE we care about is the previous red**

**//             line.**

**// FIX #3:     distance is ATR-scaled instead of a fixed point count, so**

**//             it works on Nifty, Sensex, BankNifty, and stocks alike.**

**// FIX #8:     added a warm-up pass switch matching ema200NaPasses.**

**useSTProximityFilter = input.bool(true,  title="Block Signal if EMA 200 is too close to SuperTrend (same side)", group = "Filters")**

**stProximityATRMult   = input.float(1.5, title="Min Gap: EMA 200 vs SuperTrend (x ATR)", minval=0.0, step=0.1, group = "Filters")**

**stProximityNaPasses  = input.bool(true,  title="Treat ST proximity as PASS while warming up (na)", group = "Filters")**



**extendCandles = input.int(15, title="Max Candles to wait for EMA 50 breakout (10-20)", minval=5, maxval=30, group = "Extended Setup")**



**entryCutoffHour   = input.int(15, "Stop new entries after (Hour IST)", minval=9, maxval=15, group="Session Control")**

**entryCutoffMinute = input.int(0,  "Stop new entries after (Minute)", minval=0, maxval=59, group="Session Control")**

**forceCloseHour    = input.int(15, "Force close all trades at (Hour IST)", minval=9, maxval=15, group="Session Control")**

**forceCloseMinute  = input.int(20, "Force close all trades at (Minute)", minval=0, maxval=59, group="Session Control")**



**// ==========================================**

**// FIX: Target & SL modes renamed so the active input is obvious.**

**// The previous version had "Fixed Points (Auto Nifty/Sensex)" as the default,**

**// which silently ignored "Custom Target Points" unless the user changed the**

**// dropdown. Now the mode names match what they actually do.**

**// ==========================================**

**targetMode = input.string(**

**&#x20;    "Auto (Nifty=20 / Sensex=50)",**

**&#x20;    title="Target Mode",**

**&#x20;    options=["Auto (Nifty=20 / Sensex=50)", "Custom Points", "Percentage", "ATR Multiple"],**

**&#x20;    group = "Target Settings")**



**instType = input.string("Nifty", title="Instrument (used only by Auto mode)", options=["Nifty", "Sensex"], group = "Target Settings")**

**targetPtsAuto = instType == "Nifty" ? 20 : 50**



**targetPtsCustom = input.float(20.0, title="→ [Custom Points mode] Target Points", minval=1, step=0.5, group = "Target Settings")**

**targetPct       = input.float(0.10, title="→ [Percentage mode] Target % (of entry)", minval=0.01, step=0.01, group = "Target Settings")**

**targetATRMult   = input.float(1.5,  title="→ [ATR Multiple mode] Target ATR Multiple", minval=0.1, step=0.1, group = "Target Settings")**



**slMode = input.string(**

**&#x20;    "VWAP or EMA 50 (Lower)",**

**&#x20;    title="Stop Loss Mode",**

**&#x20;    options=["VWAP or EMA 50 (Lower)", "Fixed Points", "Percentage", "ATR Multiple"],**

**&#x20;    group = "Stop Loss Settings")**



**slPtsCustom = input.float(10.0, title="→ [Fixed Points mode] SL Points", minval=1, step=0.5, group = "Stop Loss Settings")**

**slPct       = input.float(0.05, title="→ [Percentage mode] SL % (of entry)", minval=0.01, step=0.01, group = "Stop Loss Settings")**

**slATRMult   = input.float(0.8,  title="→ [ATR Multiple mode] SL ATR Multiple", minval=0.1, step=0.1, group = "Stop Loss Settings")**

**maxSLPts    = input.float(40.0, title="Max SL Distance (Points, structural mode only)", minval=1, step=0.5, group = "Stop Loss Settings")**



**vcbLength    = input.int(21, "VCB Length (Avg Volume)", minval=1, group="Volume Based Coloured Bars")**

**useVolFilter = input.bool(false, title="Require Directional Candle on Entry (Green=Long, Red=Short)", group="Volume Based Coloured Bars")**

**useGreenVolFilter  = input.bool(false, title="Require Green Candle with Volume on Long Entry", group="Volume Based Coloured Bars")**

**greenVolMultiplier = input.float(1.0, title="Long Volume Multiplier (x Average)", minval=0.1, step=0.1, group="Volume Based Coloured Bars")**

**useRedVolFilter  = input.bool(false, title="Require Red Candle with Volume on Short Entry", group="Volume Based Coloured Bars")**

**redVolMultiplier = input.float(1.0, title="Short Volume Multiplier (x Average)", minval=0.1, step=0.1, group="Volume Based Coloured Bars")**



**skipFirstN = input.int(1, title="Ignore First N Bars of Day for Signals", minval=0, maxval=15, group="Session Filter")**



**showRejections = input.bool(false, title="Show Rejection Reason Labels", group="Debug")**

**maxRejLabels   = input.int(50, title="Max Rejection Labels Per Session", minval=0, maxval=200, group="Debug")**

**showWaitMarks  = input.bool(false, title="Mark Bars Waiting for EMA50 Breakout", group="Debug")**



**// ==========================================**

**// 2. INDICATOR CALCULATIONS**

**// ==========================================**

**ema50    = ta.ema(close, emaLength)**

**ema200   = ta.ema(close, ema200Len)**

**vwapHlc3 = ta.vwap(hlc3)**

**atr      = ta.atr(atrPeriod)**



**[supertrend, direction] = ta.supertrend(factor, atrPeriod)**

**supertrend := barstate.isfirst ? na : supertrend**

**upTrend    = plot(direction < 0 ? supertrend : na, "Up Trend",   color = color.green, style = plot.style_linebr)**

**downTrend  = plot(direction < 0 ? na : supertrend, "Down Trend", color = color.red,   style = plot.style_linebr)**

**bodyMiddle = plot(barstate.isfirst ? na : (open + close) / 2, "Body Middle", display = display.none)**



**fill(bodyMiddle, upTrend,   title = "Uptrend background",   color = color.new(color.green, 90), fillgaps = false)**

**fill(bodyMiddle, downTrend, title = "Downtrend background", color = color.new(color.red,   90), fillgaps = false)**



**stGreen = direction < 0**

**stRed   = direction > 0**



**// EMA 200 gate (warm-up aware)**

**ema200Ready   = not na(ema200)**

**ema200OKLong  = not useEMA200Filter or (ema200Ready ? close > ema200 : ema200NaPasses)**

**ema200OKShort = not useEMA200Filter or (ema200Ready ? close < ema200 : ema200NaPasses)**



**// ==========================================**

**// SuperTrend Proximity Gate (Directional)**

**// ==========================================**

**prevResistanceST = direction[1] > 0 ? supertrend[1] : na**

**prevSupportST    = direction[1] < 0 ? supertrend[1] : na**



**stMinGap = atr \* stProximityATRMult**



**ema200AboveBar = not na(ema200) and ema200 > high**

**ema200BelowBar = not na(ema200) and ema200 < low**



**stGapRawLong  = (na(ema200) or na(prevResistanceST)) ? na : math.abs(ema200 - prevResistanceST)**

**stGapRawShort = (na(ema200) or na(prevSupportST))    ? na : math.abs(ema200 - prevSupportST)**



**stProxLongPassNa  = na(stGapRawLong)  ? stProximityNaPasses : false**

**stProxShortPassNa = na(stGapRawShort) ? stProximityNaPasses : false**



**stProximityOKLong  = not useSTProximityFilter or stProxLongPassNa  or not ema200AboveBar or stGapRawLong  >= stMinGap**

**stProximityOKShort = not useSTProximityFilter or stProxShortPassNa or not ema200BelowBar or stGapRawShort >= stMinGap**



**// ==========================================**

**// 3. VOLUME BASED COLOURED BARS (VCB)**

**// ==========================================**

**avrg = ta.sma(volume, vcbLength)**

**vold1 = volume > avrg \* 1.5 and close < open**

**vold2 = volume >= avrg \* 0.5 and volume <= avrg \* 1.5 and close < open**

**vold3 = volume < avrg \* 0.5 and close < open**

**volu1 = volume > avrg \* 1.5 and close > open**

**volu2 = volume >= avrg \* 0.5 and volume <= avrg \* 1.5 and close > open**

**volu3 = volume < avrg \* 0.5 and close > open**

**barColor = vold1 ? #800000 : vold2 ? #FF0000 : vold3 ? color.rgb(255, 81, 0) : volu1 ? #006400 : volu2 ? color.rgb(0, 100, 67) : volu3 ? #7FFFD4 : na**

**barcolor(barColor)**



**// ==========================================**

**// 4. TRADE STATE VARIABLES**

**// ==========================================**

**var float targetPrice   = na**

**var float stopLossPrice = na**

**var bool  isLongTrade   = true**



**var float exitedAtPrice    = na**

**var bool  exitWasTarget    = false**

**var bool  exitJustHappened = false**

**var bool  exitWasForced    = false**



**var float prevPositionSize = 0.0**

**var int   prevClosedTrades = 0**



**if barstate.isfirst**

**&#x20;   prevClosedTrades := strategy.closedtrades**



**wasFlatLastBar = prevPositionSize == 0**



**exitJustHappened := false**

**exitWasForced    := false**



**var int rejLabelCountToday = 0**



**// ==========================================**

**// 5. TARGET & SL CALCULATOR FUNCTIONS**

**// ==========================================**

**// FIX: Target mode names now match the inputs that drive them.**

**getTargetLong(entryPx) =>**

**&#x20;   switch targetMode**

**&#x20;       "Auto (Nifty=20 / Sensex=50)" => entryPx + targetPtsAuto**

**&#x20;       "Custom Points"               => entryPx + targetPtsCustom**

**&#x20;       "Percentage"                  => entryPx \* (1 + targetPct / 100)**

**&#x20;       "ATR Multiple"                => entryPx + atr \* targetATRMult**

**&#x20;       => entryPx + targetPtsAuto**



**getTargetShort(entryPx) =>**

**&#x20;   switch targetMode**

**&#x20;       "Auto (Nifty=20 / Sensex=50)" => entryPx - targetPtsAuto**

**&#x20;       "Custom Points"               => entryPx - targetPtsCustom**

**&#x20;       "Percentage"                  => entryPx \* (1 - targetPct / 100)**

**&#x20;       "ATR Multiple"                => entryPx - atr \* targetATRMult**

**&#x20;       => entryPx - targetPtsAuto**



**// maxSLPts only clamps the structural mode.**

**getSLLong(entryPx) =>**

**&#x20;   raw = switch slMode**

**&#x20;       "VWAP or EMA 50 (Lower)" => math.min(vwapHlc3, ema50)**

**&#x20;       "Fixed Points"           => entryPx - slPtsCustom**

**&#x20;       "Percentage"             => entryPx \* (1 - slPct / 100)**

**&#x20;       "ATR Multiple"           => entryPx - atr \* slATRMult**

**&#x20;       => math.min(vwapHlc3, ema50)**

**&#x20;   minGap = math.max(syminfo.mintick \* 2, entryPx \* 0.0002)**

**&#x20;   if slMode == "VWAP or EMA 50 (Lower)"**

**&#x20;       floorPx = entryPx - maxSLPts**

**&#x20;       capped  = math.max(raw, floorPx)**

**&#x20;       na(capped) ? na : math.min(capped, entryPx - minGap)**

**&#x20;   else**

**&#x20;       na(raw) ? na : math.min(raw, entryPx - minGap)**



**getSLShort(entryPx) =>**

**&#x20;   raw = switch slMode**

**&#x20;       "VWAP or EMA 50 (Lower)" => math.max(vwapHlc3, ema50)**

**&#x20;       "Fixed Points"           => entryPx + slPtsCustom**

**&#x20;       "Percentage"             => entryPx \* (1 + slPct / 100)**

**&#x20;       "ATR Multiple"           => entryPx + atr \* slATRMult**

**&#x20;       => math.max(vwapHlc3, ema50)**

**&#x20;   minGap = math.max(syminfo.mintick \* 2, entryPx \* 0.0002)**

**&#x20;   if slMode == "VWAP or EMA 50 (Lower)"**

**&#x20;       ceilPx = entryPx + maxSLPts**

**&#x20;       capped = math.min(raw, ceilPx)**

**&#x20;       na(capped) ? na : math.max(capped, entryPx + minGap)**

**&#x20;   else**

**&#x20;       na(raw) ? na : math.max(raw, entryPx + minGap)**



**// ==========================================**

**// 6. EMA 200 DISTANCE FILTER**

**// ==========================================**

**ema200DistanceOKLong(entryPx, tgtPx, tgtPts) =>**

**&#x20;   if not useEMA200DistFilter or not ema200Ready**

**&#x20;       true**

**&#x20;   else**

**&#x20;       minDistance     = tgtPts \* ema200DistMult**

**&#x20;       ema200InPath    = (ema200 >= entryPx) and (ema200 <= tgtPx)**

**&#x20;       ema200TooClose  = (ema200 > entryPx) and ((ema200 - entryPx) < minDistance)**

**&#x20;       ema200Rising    = ema200 > ema200[1] and ema200[1] > ema200[2]**

**&#x20;       ema200NearBelow = ema200CheckRising and (ema200 <= entryPx) and ((entryPx - ema200) < minDistance) and ema200Rising**

**&#x20;       not (ema200InPath or ema200TooClose or ema200NearBelow)**



**ema200DistanceOKShort(entryPx, tgtPx, tgtPts) =>**

**&#x20;   if not useEMA200DistFilter or not ema200Ready**

**&#x20;       true**

**&#x20;   else**

**&#x20;       minDistance     = tgtPts \* ema200DistMult**

**&#x20;       ema200InPath    = (ema200 <= entryPx) and (ema200 >= tgtPx)**

**&#x20;       ema200TooClose  = (ema200 < entryPx) and ((entryPx - ema200) < minDistance)**

**&#x20;       ema200Falling   = ema200 < ema200[1] and ema200[1] < ema200[2]**

**&#x20;       ema200NearAbove = ema200CheckRising and (ema200 >= entryPx) and ((ema200 - entryPx) < minDistance) and ema200Falling**

**&#x20;       not (ema200InPath or ema200TooClose or ema200NearAbove)**



**// ==========================================**

**// 7. SESSION FILTERS**

**// ==========================================**

**isNewDayRaw = timeframe.change("D")**



**var int barsSinceDayStart = 0**

**if isNewDayRaw**

**&#x20;   barsSinceDayStart := 0**

**&#x20;   rejLabelCountToday := 0**

**else**

**&#x20;   barsSinceDayStart += 1**



**isFirstCandle = barsSinceDayStart < skipFirstN**



**hourIST   = hour(time, "Asia/Kolkata")**

**minuteIST = minute(time, "Asia/Kolkata")**



**isPastEntryCutoff = (hourIST > entryCutoffHour) or (hourIST == entryCutoffHour and minuteIST >= entryCutoffMinute)**

**isForceCloseTime  = (hourIST > forceCloseHour) or (hourIST == forceCloseHour and minuteIST >= forceCloseMinute)**



**signalAllowed = not isFirstCandle and not isPastEntryCutoff and not isForceCloseTime**



**// ==========================================**

**// 8. CANDLE + VOLUME FILTERS**

**// ==========================================**

**isGreenCandle  = close > open**

**isRedCandle    = close < open**

**hasVolumeLong  = volume > avrg \* greenVolMultiplier**

**hasVolumeShort = volume > avrg \* redVolMultiplier**



**greenVolFilterOK = not useGreenVolFilter or (isGreenCandle and hasVolumeLong)**

**redVolFilterOK   = not useRedVolFilter   or (isRedCandle   and hasVolumeShort)**



**// ==========================================**

**// 9. FLIP DETECTION**

**// ==========================================**

**flipToGreen = stGreen and not stGreen[1]**

**flipToRed   = stRed   and not stRed[1]**



**// ==========================================**

**// 10. LONG SIDE LOGIC**

**// ==========================================**

**var bool waitingForBreakLong = false**

**var int  candlesWaitedLong   = 0**



**if stRed or strategy.position_size != 0 or isNewDayRaw**

**&#x20;   waitingForBreakLong := false**

**&#x20;   candlesWaitedLong   := 0**



**if enableLong and flipToGreen and strategy.position_size == 0 and signalAllowed**

**&#x20;   primaryVwapOK = not useVWAPAtFlip or (close > vwapHlc3)**

**&#x20;   aboveEMA50    = close > ema50**

**&#x20;   volOK         = not useVolFilter or isGreenCandle**



**&#x20;   testTarget    = getTargetLong(close)**

**&#x20;   testTargetPts = testTarget - close**

**&#x20;   distOK        = ema200DistanceOKLong(close, testTarget, testTargetPts)**



**&#x20;   if aboveEMA50 and primaryVwapOK and ema200OKLong and volOK and distOK and greenVolFilterOK and stProximityOKLong**

**&#x20;       waitingForBreakLong := false**

**&#x20;       candlesWaitedLong   := 0**

**&#x20;       strategy.entry("Long", strategy.long, comment="Primary L")**

**&#x20;   else if aboveEMA50 and primaryVwapOK and ema200OKLong and volOK and distOK and greenVolFilterOK and not stProximityOKLong**

**&#x20;       waitingForBreakLong := false**

**&#x20;       candlesWaitedLong   := 0**

**&#x20;   else if aboveEMA50 and primaryVwapOK and ema200OKLong and volOK and not distOK**

**&#x20;       waitingForBreakLong := false**

**&#x20;       candlesWaitedLong   := 0**

**&#x20;   else**

**&#x20;       waitingForBreakLong := true**

**&#x20;       candlesWaitedLong   := 0**



**if enableLong and waitingForBreakLong and strategy.position_size == 0 and not flipToGreen**

**&#x20;   breakVwapOK = not useVWAPAtBreak or (close > vwapHlc3)**

**&#x20;   volOK       = not useVolFilter or isGreenCandle**

**&#x20;   entered     = false**



**&#x20;   if signalAllowed and close > ema50 and breakVwapOK and ema200OKLong and volOK and greenVolFilterOK and stProximityOKLong**

**&#x20;       testTarget    = getTargetLong(close)**

**&#x20;       testTargetPts = testTarget - close**

**&#x20;       if ema200DistanceOKLong(close, testTarget, testTargetPts)**

**&#x20;           waitingForBreakLong := false**

**&#x20;           candlesWaitedLong   := 0**

**&#x20;           entered             := true**

**&#x20;           strategy.entry("Long", strategy.long, comment="Extended L")**



**&#x20;   if not entered**

**&#x20;       if signalAllowed**

**&#x20;           candlesWaitedLong += 1**

**&#x20;       if candlesWaitedLong >= extendCandles**

**&#x20;           waitingForBreakLong := false**

**&#x20;           candlesWaitedLong   := 0**



**// ==========================================**

**// 11. SHORT SIDE LOGIC**

**// ==========================================**

**var bool waitingForBreakShort = false**

**var int  candlesWaitedShort   = 0**



**if stGreen or strategy.position_size != 0 or isNewDayRaw**

**&#x20;   waitingForBreakShort := false**

**&#x20;   candlesWaitedShort   := 0**



**if enableShort and flipToRed and strategy.position_size == 0 and signalAllowed**

**&#x20;   primaryVwapOK = not useVWAPAtFlip or (close < vwapHlc3)**

**&#x20;   belowEMA50    = close < ema50**

**&#x20;   volOK         = not useVolFilter or isRedCandle**



**&#x20;   testTarget    = getTargetShort(close)**

**&#x20;   testTargetPts = close - testTarget**

**&#x20;   distOK        = ema200DistanceOKShort(close, testTarget, testTargetPts)**



**&#x20;   if belowEMA50 and primaryVwapOK and ema200OKShort and volOK and distOK and redVolFilterOK and stProximityOKShort**

**&#x20;       waitingForBreakShort := false**

**&#x20;       candlesWaitedShort   := 0**

**&#x20;       strategy.entry("Short", strategy.short, comment="Primary S")**

**&#x20;   else if belowEMA50 and primaryVwapOK and ema200OKShort and volOK and distOK and redVolFilterOK and not stProximityOKShort**

**&#x20;       waitingForBreakShort := false**

**&#x20;       candlesWaitedShort   := 0**

**&#x20;   else if belowEMA50 and primaryVwapOK and ema200OKShort and volOK and not distOK**

**&#x20;       waitingForBreakShort := false**

**&#x20;       candlesWaitedShort   := 0**

**&#x20;   else**

**&#x20;       waitingForBreakShort := true**

**&#x20;       candlesWaitedShort   := 0**



**if enableShort and waitingForBreakShort and strategy.position_size == 0 and not flipToRed**

**&#x20;   breakVwapOK = not useVWAPAtBreak or (close < vwapHlc3)**

**&#x20;   volOK       = not useVolFilter or isRedCandle**

**&#x20;   enteredS    = false**



**&#x20;   if signalAllowed and close < ema50 and breakVwapOK and ema200OKShort and volOK and redVolFilterOK and stProximityOKShort**

**&#x20;       testTarget    = getTargetShort(close)**

**&#x20;       testTargetPts = close - testTarget**

**&#x20;       if ema200DistanceOKShort(close, testTarget, testTargetPts)**

**&#x20;           waitingForBreakShort := false**

**&#x20;           candlesWaitedShort   := 0**

**&#x20;           enteredS             := true**

**&#x20;           strategy.entry("Short", strategy.short, comment="Extended S")**



**&#x20;   if not enteredS**

**&#x20;       if signalAllowed**

**&#x20;           candlesWaitedShort += 1**

**&#x20;       if candlesWaitedShort >= extendCandles**

**&#x20;           waitingForBreakShort := false**

**&#x20;           candlesWaitedShort   := 0**



**// ==========================================**

**// 12. ENTRY SNAPSHOT — Target/SL from FILL PRICE**

**// ==========================================**

**if strategy.position_size != 0 and na(targetPrice)**

**&#x20;   actualEntry = strategy.position_avg_price**

**&#x20;   if not na(actualEntry)**

**&#x20;       storedEntry  := actualEntry**

**&#x20;       storedTarget := targetPrice**

**&#x20;       storedSL     := stopLossPrice**

**&#x20;       if strategy.position_size > 0**

**&#x20;           targetPrice   := getTargetLong(actualEntry)**

**&#x20;           stopLossPrice := getSLLong(actualEntry)**

**&#x20;           isLongTrade   := true**

**&#x20;       else**

**&#x20;           targetPrice   := getTargetShort(actualEntry)**

**&#x20;           stopLossPrice := getSLShort(actualEntry)**

**&#x20;           isLongTrade   := false**



**if strategy.position_size != 0 and not na(targetPrice) and ((strategy.position_size > 0) != isLongTrade)**

**&#x20;   reEntry = strategy.position_avg_price**

**&#x20;   if not na(reEntry)**

**&#x20;       isLongTrade   := strategy.position_size > 0**

**&#x20;       targetPrice   := isLongTrade ? getTargetLong(reEntry)  : getTargetShort(reEntry)**

**&#x20;       stopLossPrice := isLongTrade ? getSLLong(reEntry)      : getSLShort(reEntry)**



**// ==========================================**

**// 13. EXIT LOGIC**

**// ==========================================**

**if strategy.position_size > 0 and not na(targetPrice) and not na(stopLossPrice)**

**&#x20;   strategy.exit("Exit L", from_entry="Long", stop=stopLossPrice, limit=targetPrice)**



**if strategy.position_size < 0 and not na(targetPrice) and not na(stopLossPrice)**

**&#x20;   strategy.exit("Exit S", from_entry="Short", stop=stopLossPrice, limit=targetPrice)**



**forceCloseNow = (isForceCloseTime or isNewDayRaw) and strategy.position_size != 0**

**if forceCloseNow**

**&#x20;   exitWasForced := true**

**&#x20;   strategy.close_all(comment = isNewDayRaw ? "EOD-NewDay" : "EOD")**



**closedTradesNow = strategy.closedtrades**

**justClosedTrade = closedTradesNow > prevClosedTrades**



**if justClosedTrade**

**&#x20;   lastIdx    = closedTradesNow - 1**

**&#x20;   realExitPx = strategy.closedtrades.exit_price(lastIdx)**

**&#x20;   exitedAtPrice := realExitPx**



**&#x20;   lastComment = strategy.closedtrades.exit_comment(lastIdx)**

**&#x20;   wasEOD      = lastComment == "EOD" or lastComment == "EOD-NewDay"**



**&#x20;   if wasEOD**

**&#x20;       exitWasTarget := false**

**&#x20;   else if not na(targetPrice) and not na(realExitPx)**

**&#x20;       tol = syminfo.mintick \* 2**

**&#x20;       exitWasTarget := isLongTrade ? realExitPx >= targetPrice - tol : realExitPx <= targetPrice + tol**

**&#x20;   else**

**&#x20;       exitWasTarget := false**



**&#x20;   exitJustHappened := true**

**&#x20;   prevClosedTrades := closedTradesNow**



**if strategy.position_size == 0**

**&#x20;   targetPrice   := na**

**&#x20;   stopLossPrice := na**



**// ==========================================**

**// 14. PLOTTING**

**// ==========================================**

**plot(ema50,    color=color.new(color.blue,   0), title="EMA 50",     linewidth=2)**

**plot(ema200,   color=color.new(color.purple, 0), title="EMA 200",    linewidth=2)**

**plot(vwapHlc3, color=color.new(color.orange, 0), title="VWAP (HLC3)", linewidth=2)**



**newEntryFilled = strategy.position_size != 0 and wasFlatLastBar**



**if newEntryFilled and not na(targetPrice) and not na(stopLossPrice)**

**&#x20;   entryPx = strategy.position_avg_price**

**&#x20;   isLong  = strategy.position_size > 0**

**&#x20;   labelText  = (isLong ? "BUY @ " : "SELL @ ") + str.tostring(entryPx, "#.00") + "\nTGT: " + str.tostring(targetPrice, "#.00") + "\nSL: " + str.tostring(stopLossPrice, "#.00")**

**&#x20;   labelColor = isLong ? color.new(color.green, 0) : color.new(color.red, 0)**

**&#x20;   labelStyle = isLong ? label.style_label_up : label.style_label_down**

**&#x20;   ylocUse    = isLong ? yloc.belowbar : yloc.abovebar**

**&#x20;   yPx        = isLong ? low : high**

**&#x20;   label.new(bar_index, yPx, text = labelText, style = labelStyle, color = labelColor, textcolor = color.white, size = size.small, yloc = ylocUse)**



**if exitJustHappened**

**&#x20;   exitLabelColor = exitWasTarget ? color.new(color.blue, 0) : color.new(color.orange, 0)**

**&#x20;   exitLabelStyle = isLongTrade ? label.style_label_down : label.style_label_up**

**&#x20;   exitYlocUse    = isLongTrade ? yloc.abovebar : yloc.belowbar**

**&#x20;   exitYPx        = isLongTrade ? high : low**

**&#x20;   exitText       = (exitWasTarget ? "TARGET HIT @ " : "EXIT @ ") + str.tostring(exitedAtPrice, "#.00")**

**&#x20;   label.new(bar_index, exitYPx, text = exitText, style = exitLabelStyle, color = exitLabelColor, textcolor = color.white, size = size.small, yloc = exitYlocUse)**



**plot(strategy.position_size != 0 ? targetPrice   : na, title="Target Level",    color=color.yellow, style=plot.style_linebr, linewidth=2)**

**plot(strategy.position_size != 0 ? stopLossPrice : na, title="Stop Loss Level", color=color.red,    style=plot.style_linebr, linewidth=2)**



**// ==========================================**

**// 15. DEBUG — why a flip did NOT produce a signal**

**// ==========================================**

**rejBudgetOK = rejLabelCountToday < maxRejLabels**



**if showRejections and rejBudgetOK and flipToGreen and strategy.position_size == 0**

**&#x20;   tgt = getTargetLong(close)**

**&#x20;   r = ""**

**&#x20;   r += not signalAllowed ? "session " : ""**

**&#x20;   r += close <= ema50 ? "ema50 " : ""**

**&#x20;   r += (useVWAPAtFlip and close <= vwapHlc3) ? "vwap " : ""**

**&#x20;   r += (useEMA200Filter and not ema200Ready and not ema200NaPasses) ? "ema200-warmup " : ""**

**&#x20;   r += (useEMA200Filter and ema200Ready and close <= ema200) ? "ema200 " : ""**

**&#x20;   r += not ema200DistanceOKLong(close, tgt, tgt - close) ? "ema200-dist " : ""**

**&#x20;   r += not stProximityOKLong ? "st-prox " : ""**

**&#x20;   r += not greenVolFilterOK ? "vol " : ""**

**&#x20;   r += not enableLong ? "disabled " : ""**

**&#x20;   if r != ""**

**&#x20;       label.new(bar_index, low, "REJ L: " + r, style=label.style_label_up, color=color.new(color.gray, 20), textcolor=color.white, size=size.tiny, yloc=yloc.belowbar)**

**&#x20;       rejLabelCountToday += 1**



**if showRejections and rejBudgetOK and flipToRed and strategy.position_size == 0**

**&#x20;   tgtS = getTargetShort(close)**

**&#x20;   rs = ""**

**&#x20;   rs += not signalAllowed ? "session " : ""**

**&#x20;   rs += close >= ema50 ? "ema50 " : ""**

**&#x20;   rs += (useVWAPAtFlip and close >= vwapHlc3) ? "vwap " : ""**

**&#x20;   rs += (useEMA200Filter and not ema200Ready and not ema200NaPasses) ? "ema200-warmup " : ""**

**&#x20;   rs += (useEMA200Filter and ema200Ready and close >= ema200) ? "ema200 " : ""**

**&#x20;   rs += not ema200DistanceOKShort(close, tgtS, close - tgtS) ? "ema200-dist " : ""**

**&#x20;   rs += not stProximityOKShort ? "st-prox " : ""**

**&#x20;   rs += not redVolFilterOK ? "vol " : ""**

**&#x20;   rs += not enableShort ? "disabled " : ""**

**&#x20;   if rs != ""**

**&#x20;       label.new(bar_index, high, "REJ S: " + rs, style=label.style_label_down, color=color.new(color.gray, 20), textcolor=color.white, size=size.tiny, yloc=yloc.abovebar)**

**&#x20;       rejLabelCountToday += 1**



**plotshape(showWaitMarks and waitingForBreakLong,  title="Waiting L", style=shape.circle, location=location.belowbar, color=color.new(color.lime, 40),    size=size.tiny)**

**plotshape(showWaitMarks and waitingForBreakShort, title="Waiting S", style=shape.circle, location=location.abovebar, color=color.new(color.fuchsia, 40), size=size.tiny)**



**// ==========================================**

**// 16. ALERTS**

**// ==========================================**

**// ==========================================**

**// 16. ALERTS (JSON payload for webhook)**

**// ==========================================**

**&#x20;// Read strike price and CE/PE from the chart name itself.**

**// Example chart name: NIFTY260929P23050  →  strike = 23050, type = PE**

**chartSym  = syminfo.ticker**

**lastDigit = str.length(chartSym)**

**scanPos   = lastDigit**



**// Walk backwards to find where the strike digits start**

**while scanPos > 0**

**&#x20;   ch = str.substring(chartSym, scanPos - 1, scanPos)**

**&#x20;   if str.contains("0123456789", ch)**

**&#x20;       scanPos -= 1**

**&#x20;   else**

**&#x20;       break**



**strikeStr   = str.substring(chartSym, scanPos, lastDigit)**

**optLetter   = str.substring(chartSym, scanPos - 1, scanPos)**

**strikeValue = str.tonumber(strikeStr)**

**optTypeStr  = optLetter == "C" ? "CE" : "PE"**



**// ---- ENTRY ALERT ----**

**if newEntryFilled and not na(targetPrice) and not na(stopLossPrice) and strategy.position_size != 0**

**&#x20;   entryPx  = strategy.position_avg_price**

**&#x20;   isLong   = strategy.position_size > 0**

**&#x20;   riskPts  = isLong ? (entryPx - stopLossPrice) : (stopLossPrice - entryPx)**

**&#x20;   rewardPts= isLong ? (targetPrice - entryPx) : (entryPx - targetPrice)**



**&#x20;   msg = '{"chart":"'      + chartSym +**

**&#x20;         '","strike":'     + str.tostring(strikeValue, "#") +**

**&#x20;         ',"type":"'       + optTypeStr +**

**&#x20;         '","side":"'      + (isLong ? "BUY" : "SELL") +**

**&#x20;         '","entry":'      + str.tostring(entryPx,     "#.00") +**

**&#x20;         ',"target":'      + str.tostring(targetPrice, "#.00") +**

**&#x20;         ',"sl":'          + str.tostring(stopLossPrice, "#.00") +**

**&#x20;         ',"riskPts":'     + str.tostring(riskPts,     "#.00") +**

**&#x20;         ',"rewardPts":'   + str.tostring(rewardPts,   "#.00") +**

**&#x20;         '}'**

**&#x20;   alert(msg, alert.freq_once_per_bar_close)**



**&#x20;// Exit alert intentionally disabled — only entry alerts fire.**

**// ==========================================**

**// Commit prevPositionSize LAST, after every reader.**

**// ==========================================**

**prevPositionSize := strategy.position_size**