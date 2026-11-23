class MidasTouch2NoQuotaResearch {
  lastKey:string="";
  volumeRejects:number=0;
  fibRejects:number=0;
  lastEntryTime:number=0;
  entryTime:number=0;
  activeLotId:number=-1;
  tp1Done:boolean=false;
  tp2Done:boolean=false;
  runnerTrailArmed:boolean=false;
  tradeRisk:number=0;
  tradeStates:any[]=[];
  entryAttributionRecords:string[]=[];
  dayKey:number=-1;
  currentDayEligible:boolean=false;
  lastFinalizedDay:number=-1;
  entriesToday:number=0;
  daysObserved:number=0;
  daysMetMinimum:number=0;
  daysBelowMinimum:number=0;
  dailyEntrySum:number=0;
  dailyShortfallSum:number=0;
  maxEntriesInDay:number=0;
  totalEntriesPlaced:number=0;
  strictEntries:number=0;
  singleSwingEntries:number=0;
  continuationEntries:number=0;
  microMomentumEntries:number=0;
  lastEngineClosedTrades:number=0;
  observedCloseUpdates:number=0;
  missedCloseEvents:number=0;
  tierPositionN:number[]=[];
  tierPositionW:number[]=[];
  tierPositionL:number[]=[];
  tierPositionPnl:number[]=[];
  // Entry-time feature snapshots and final outcomes; telemetry only.
  featureWinSums:number[]=[];
  featureLossSums:number[]=[];
  featureWinN:number=0;
  featureLossN:number=0;
  regimePositionN:number[]=[];
  regimePositionW:number[]=[];
  regimePositionL:number[]=[];

  blockedOpposite:number=0;
  blockedRiskCap:number=0;
  blockedConcurrency:number=0;
  blockedDailyMax:number=0;
  weekendFlattenCalls:number=0;
  weekendFlattenErrors:number=0;
  weekendLotsTargeted:number=0;
  weekendBlockedEntryBars:number=0;
  blockedSingleSwingRegime:number=0;
  blockedContinuationRegime:number=0;
  dualLaneSingleSwingCandidates:number=0;
  dualLaneContinuationCandidates:number=0;
  dualLaneCompetitionBars:number=0;
  dualLaneSingleSwingSelections:number=0;
  dualLaneContinuationSelections:number=0;
  blockedStops:number=0;
  blockedSizing:number=0;
  tp1Count:number=0;
  tp2Count:number=0;

  // Preserve instrument-native price precision in keys and entry lineage.
  // Two-decimal rounding collides distinct FX prices; fixed five decimals also
  // truncates some higher-precision feeds. priceDigits comes from the active feed.
  pricePrecision(ctx:Context):number {
    const d=ctx.symbol.priceDigits;
    return Number.isFinite(d)?Math.max(0,Math.min(10,Math.floor(d))):5;
  }

  priceKey(ctx:Context,value:number):string {
    return value.toFixed(this.pricePrecision(ctx));
  }

  onInit(ctx:InitContext):void {
    this.lastKey="";
    this.lastEntryTime=0;
    this.entryTime=0;
    this.activeLotId=-1;
    this.tp1Done=false;
    this.tp2Done=false;
    this.runnerTrailArmed=false;
    this.tradeRisk=0;
    this.tradeStates=[];
    this.entryAttributionRecords=[];
    this.dayKey=-1; this.currentDayEligible=false; this.lastFinalizedDay=-1; this.entriesToday=0;
    this.daysObserved=0; this.daysMetMinimum=0; this.daysBelowMinimum=0;
    this.dailyEntrySum=0; this.dailyShortfallSum=0; this.maxEntriesInDay=0;
    this.totalEntriesPlaced=0; this.strictEntries=0; this.singleSwingEntries=0; this.continuationEntries=0; this.microMomentumEntries=0;
    this.lastEngineClosedTrades=0;
    this.observedCloseUpdates=0;
    this.missedCloseEvents=0;
    this.tierPositionN=[0,0,0,0,0]; this.tierPositionW=[0,0,0,0,0]; this.tierPositionL=[0,0,0,0,0]; this.tierPositionPnl=[0,0,0,0,0];
    this.featureWinSums=[0,0,0,0,0,0,0,0,0,0,0,0];
    this.featureLossSums=[0,0,0,0,0,0,0,0,0,0,0,0];
    this.featureWinN=0; this.featureLossN=0;
    this.regimePositionN=[0,0,0]; this.regimePositionW=[0,0,0]; this.regimePositionL=[0,0,0];
    this.blockedOpposite=0; this.blockedRiskCap=0; this.blockedConcurrency=0; this.blockedDailyMax=0;
    this.weekendFlattenCalls=0; this.weekendFlattenErrors=0;
    this.weekendLotsTargeted=0; this.weekendBlockedEntryBars=0;
    this.blockedSingleSwingRegime=0; this.blockedContinuationRegime=0;
    this.dualLaneSingleSwingCandidates=0; this.dualLaneContinuationCandidates=0;
    this.dualLaneCompetitionBars=0; this.dualLaneSingleSwingSelections=0;
    this.dualLaneContinuationSelections=0;
    this.blockedStops=0; this.blockedSizing=0; this.tp1Count=0; this.tp2Count=0;
  }

  atr(ctx:Context, back:number):number {
    const n=ctx.inputs.atrLen;
    if(ctx.bars.count < back+n+2) return NaN;
    let sum=0;
    for(let i=back;i<back+n;i++){
      const h=ctx.bars.high(i), l=ctx.bars.low(i), pc=ctx.bars.close(i+1);
      sum += Math.max(h-l,Math.abs(h-pc),Math.abs(l-pc));
    }
    return sum/n;
  }

  // Research regime proxy: absolute 8-vs-21 bar mean separation / ATR.
  // 0=range-like, 1=transition, 2=trend-like. This is not the production EA classifier.
  trendSlopeProxyATR(ctx:Context):number {
    const a=this.atr(ctx,1);
    if(!(a>0)||ctx.bars.count<25)return NaN;
    let fast=0,slow=0;
    for(let k=1;k<=8;k++)fast+=ctx.bars.close(k);
    for(let k=1;k<=21;k++)slow+=ctx.bars.close(k);
    return Math.abs(fast/8-slow/21)/a;
  }

  bodyRatio(ctx:Context,i:number):number {
    const r=ctx.bars.high(i)-ctx.bars.low(i);
    return r>0 ? Math.abs(ctx.bars.close(i)-ctx.bars.open(i))/r : 0;
  }

  isSwingHigh(ctx:Context,i:number):boolean {
    const s=ctx.inputs.swingStrength;
    if(i < s+1 || i+s >= ctx.bars.count) return false;
    const x=ctx.bars.high(i);
    for(let d=1;d<=s;d++){
      if(x < ctx.bars.high(i-d) || x < ctx.bars.high(i+d)) return false;
    }
    return true;
  }

  isSwingLow(ctx:Context,i:number):boolean {
    const s=ctx.inputs.swingStrength;
    if(i < s+1 || i+s >= ctx.bars.count) return false;
    const x=ctx.bars.low(i);
    for(let d=1;d<=s;d++){
      if(x > ctx.bars.low(i-d) || x > ctx.bars.low(i+d)) return false;
    }
    return true;
  }

  inSession(ctx:Context):boolean {
    const h=new Date(ctx.time).getUTCHours();
    return h>=ctx.inputs.sessionStartUTC && h<ctx.inputs.sessionEndUTC;
  }

  // Research-only weekend guard. It blocks entries throughout Saturday and
  // Sunday, and from Friday's UTC cutoff onward. At the first eligible market
  // update it submits one account-wide flatten request instead of closing
  // lots one by one. Any multi-lot close-event collision invalidates the
  // internal attribution tracker; full-position results must then be rebuilt
  // from the saved session rows grouped by original opening fill.
  applyWeekendGuard(ctx:Context):boolean {
    if(!ctx.inputs.avoidWeekendExposure)return false;
    const date=new Date(ctx.time);
    const day=date.getUTCDay();
    const hour=date.getUTCHours();
    const weekend=day===6 || day===0 || (day===5 && hour>=ctx.inputs.fridayCutoffHourUTC);
    if(!weekend)return false;
    if(ctx.isNewBar)this.weekendBlockedEntryBars++;
    const lots=ctx.account.lots;
    if(lots.length>0){
      try {
        this.weekendFlattenCalls++;
        this.weekendLotsTargeted+=lots.length;
        ctx.orders.closePosition();
        this.captureLastClosed(ctx);
        if(ctx.account.lots.length>0)this.weekendFlattenErrors++;
      } catch(e:any) {
        this.weekendFlattenErrors++;
      }
    }
    return true;
  }

  findLiquidity(ctx:Context,forBuy:boolean):any {
    const start=Math.max(ctx.inputs.swingStrength+1,3);
    const end=Math.min(ctx.inputs.lookbackBars,ctx.bars.count-ctx.inputs.swingStrength-1);
    let best:any=null;

    for(let a=start;a<=end;a++){
      if(forBuy ? !this.isSwingLow(ctx,a) : !this.isSwingHigh(ctx,a)) continue;
      const p=forBuy ? ctx.bars.low(a) : ctx.bars.high(a);
      const aa=this.atr(ctx,a);
      if(!(aa>0)) continue;

      for(let b=a+1;b<=end;b++){
        if(forBuy ? !this.isSwingLow(ctx,b) : !this.isSwingHigh(ctx,b)) continue;
        const q=forBuy ? ctx.bars.low(b) : ctx.bars.high(b);
        if(Math.abs(p-q)>ctx.inputs.equalTolATR*aa) continue;

        const pool=forBuy ? Math.min(p,q) : Math.max(p,q);
        const confirm=Math.min(a,b);
        const newestSweep=Math.max(1,confirm-1);
        const oldestSweep=Math.max(1,Math.min(end-1,confirm-ctx.inputs.maxSweepAgeBars));
        for(let sw=newestSweep;sw>=oldestSweep;sw--){
          if(forBuy){
            if(!(ctx.bars.low(sw)<pool && ctx.bars.close(sw)>pool)) continue;
            const atr=this.atr(ctx,sw);
            if(!(atr>0)) continue;
            const wick=pool-ctx.bars.low(sw);
            const reclaim=ctx.bars.close(sw)-pool;
            const ratio=wick>0?Math.max(0,Math.min(reclaim/wick,1)):0;
            if(ratio<ctx.inputs.minRejectionRatio) continue;
            const pen=wick/atr;
            const key="L:"+sw+":"+this.priceKey(ctx,pool);
            best={sw,pool,ratio,pen,key};
          } else {
            if(!(ctx.bars.high(sw)>pool && ctx.bars.close(sw)<pool)) continue;
            const atr=this.atr(ctx,sw);
            if(!(atr>0)) continue;
            const wick=ctx.bars.high(sw)-pool;
            const reclaim=pool-ctx.bars.close(sw);
            const ratio=wick>0?Math.max(0,Math.min(reclaim/wick,1)):0;
            if(ratio<ctx.inputs.minRejectionRatio) continue;
            const pen=wick/atr;
            const key="S:"+sw+":"+this.priceKey(ctx,pool);
            best={sw,pool,ratio,pen,key};
          }
          return best;
        }
      }
    }
    return null;
  }

  findStructure(ctx:Context,forBuy:boolean,sw:number):any {
    const start=Math.max(ctx.inputs.swingStrength+1,3);
    const maxPivot=Math.min(ctx.inputs.lookbackBars,ctx.bars.count-ctx.inputs.swingStrength-1);
    for(let pivot=sw+1;pivot<=maxPivot;pivot++){
      if(forBuy ? !this.isSwingHigh(ctx,pivot) : !this.isSwingLow(ctx,pivot)) continue;
      const level=forBuy?ctx.bars.high(pivot):ctx.bars.low(pivot);
      for(let bos=pivot-1;bos>=1;bos--){
        if(bos>ctx.inputs.maxStructureAgeBars) continue;
        const atr=this.atr(ctx,bos);
        if(!(atr>0)) continue;
        const crossed=forBuy ? ctx.bars.close(bos)>level+0.1*atr : ctx.bars.close(bos)<level-0.1*atr;
        if(!crossed) continue;
        const dist=forBuy ? (ctx.bars.close(bos)-level)/atr : (level-ctx.bars.close(bos))/atr;
        const br=this.bodyRatio(ctx,bos);
        const strength=Math.max(0,Math.min(1,0.6*Math.min(dist/1,1)+0.4*Math.min(br/0.75,1)));
        return {pivot,bos,level,strength};
      }
    }
    return null;
  }

  findDisplacement(ctx:Context,forBuy:boolean,sw:number,bos:number):any {
    const oldest=Math.min(sw-1,bos+ctx.inputs.maxSweepAgeBars);
    for(let i=bos;i<=oldest;i++){
      const atr=this.atr(ctx,i);
      if(!(atr>0)) continue;
      const range=ctx.bars.high(i)-ctx.bars.low(i);
      if(!(range>0)) continue;
      const directional=forBuy ? ctx.bars.close(i)>ctx.bars.open(i) : ctx.bars.close(i)<ctx.bars.open(i);
      const ra=range/atr;
      if(!directional || ra<ctx.inputs.minDisplacementATR) continue;
      const br=this.bodyRatio(ctx,i);
      if(br<ctx.inputs.minBodyRatio) continue;
      return {bar:i,atr,rangeATR:ra,bodyRatio:br};
    }
    return null;
  }

  findFVG(ctx:Context,forBuy:boolean,bos:number,disp:number,sw:number):any {
    const newest=Math.max(1,bos);
    const oldest=Math.min(ctx.bars.count-3,disp+ctx.inputs.maxStructureToFVG);
    let best:any=null;
    for(let mid=newest+1;mid<=oldest+1;mid++){
      const newer=mid-1, older=mid+1;
      if(newer<1 || older>=ctx.bars.count) continue;
      let top=0,bottom=0;
      if(forBuy){
        if(ctx.bars.low(newer)<=ctx.bars.high(older)) continue;
        top=ctx.bars.low(newer); bottom=ctx.bars.high(older);
      } else {
        if(ctx.bars.high(newer)>=ctx.bars.low(older)) continue;
        top=ctx.bars.low(older); bottom=ctx.bars.high(newer);
      }
      const atr=this.atr(ctx,mid);
      if(!(atr>0)) continue;
      const width=Math.abs(top-bottom);
      if(width<ctx.inputs.minFVGATR*atr) continue;
      const completion=newer;
      if(completion<bos || completion>disp) continue;
      if(completion>=sw) continue;
      const age=Math.max(0,completion-1);
      if(age>ctx.inputs.maxStructureAgeBars) continue;
      const price=ctx.bars.close(1);
      const midPrice=(top+bottom)/2;
      const dist=Math.abs(price-midPrice)/this.atr(ctx,1);
      if(dist>ctx.inputs.maxFVGDistanceATR) continue;
      best={top,bottom,widthATR:width/atr,completion,age};
      break;
    }
    return best;
  }

  locationOK(ctx:Context,forBuy:boolean,pivot:number,fvgMid:number):boolean {
    let hi=-Infinity,lo=Infinity;
    const limit=Math.min(ctx.inputs.lookbackBars,ctx.bars.count-ctx.inputs.swingStrength-1);
    const start=Math.max(pivot+1,ctx.inputs.swingStrength+1);
    for(let i=start;i<=limit;i++){
      if(this.isSwingHigh(ctx,i)) hi=Math.max(hi,ctx.bars.high(i));
      if(this.isSwingLow(ctx,i)) lo=Math.min(lo,ctx.bars.low(i));
    }
    if(!(hi>lo) || !isFinite(fvgMid)) return false;
    const mid=lo+0.5*(hi-lo);
    return forBuy ? fvgMid<=mid : fvgMid>=mid;
  }



  rvol(ctx:Context):number {
    const n=ctx.inputs.rvolLookback;
    if(ctx.bars.count<n+3) return 0;
    let sum=0;
    for(let i=2;i<=n+1;i++) sum+=ctx.bars.volume(i);
    const avg=sum/n;
    return avg>0 ? ctx.bars.volume(1)/avg : 0;
  }

  fibInZone(ctx:Context,forBuy:boolean):boolean {
    const limit=Math.min(ctx.inputs.lookbackBars,ctx.bars.count-ctx.inputs.swingStrength-1);
    let hi=-Infinity,lo=-Infinity,hiBar=-1,loBar=-1;
    for(let i=ctx.inputs.swingStrength+1;i<=limit;i++){
      if(forBuy && this.isSwingHigh(ctx,i)){hi=ctx.bars.high(i);hiBar=i;break;}
      if(!forBuy && this.isSwingLow(ctx,i)){lo=ctx.bars.low(i);loBar=i;break;}
    }
    if(forBuy && hiBar<0) return false;
    if(!forBuy && loBar<0) return false;
    let legLow=-Infinity,legHigh=-Infinity;
    if(forBuy){
      for(let i=hiBar+1;i<=limit;i++) if(this.isSwingLow(ctx,i)){legLow=ctx.bars.low(i);break;}
      if(!(legLow>-Infinity)||!(hi>legLow)) return false;
      const pct=(hi-ctx.bars.close(1))/(hi-legLow)*100;
      const a=Math.min(ctx.inputs.fibZoneMinPct,ctx.inputs.fibZoneMaxPct),b=Math.max(ctx.inputs.fibZoneMinPct,ctx.inputs.fibZoneMaxPct);
      return pct>=a&&pct<=b;
    } else {
      for(let i=loBar+1;i<=limit;i++) if(this.isSwingHigh(ctx,i)){legHigh=ctx.bars.high(i);break;}
      if(!(legHigh<Infinity)||!(legHigh>lo)) return false;
      const pct=(ctx.bars.close(1)-lo)/(legHigh-lo)*100;
      const a=Math.min(ctx.inputs.fibZoneMinPct,ctx.inputs.fibZoneMaxPct),b=Math.max(ctx.inputs.fibZoneMinPct,ctx.inputs.fibZoneMaxPct);
      return pct>=a&&pct<=b;
    }
  }
  optionalFiltersOK(ctx:Context,forBuy:boolean):boolean {
    if(ctx.inputs.requireVolumeConfirmation && this.rvol(ctx)<ctx.inputs.rvolThreshold){
      this.volumeRejects++;
      return false;
    }
    if(ctx.inputs.requireFibonacciZone && !this.fibInZone(ctx,forBuy)){
      this.fibRejects++;
      return false;
    }
    return true;
  }

  openRiskPercent(ctx:Context):number {
    const lots=ctx.account.lots;
    let riskMoney=0;
    for(let i=0;i<lots.length;i++){
      const lot=lots[i];
      const idx=this.stateIndex(lot.lotId);
      if(idx<0)return Infinity;
      const state=this.tradeStates[idx];
      if(!(state.initialQuantity>0)||!(state.riskMoney>0)||!(lot.quantity>0))return Infinity;
      if(lot.stopLossPrice===null && lot.trailPrice===null)return Infinity;
      const remaining=Math.min(1,Math.max(0,lot.quantity/state.initialQuantity));
      riskMoney+=state.riskMoney*remaining;
    }
    const balance=ctx.account.balance;
    return balance>0 ? 100*riskMoney/balance : Infinity;
  }

  chain(ctx:Context,forBuy:boolean):any {
    const liq=this.findLiquidity(ctx,forBuy);
    if(liq===null) return null;

    const st=this.findStructure(ctx,forBuy,liq.sw);
    if(st===null) return null;

    const disp=this.findDisplacement(ctx,forBuy,liq.sw,st.bos);
    if(disp===null) return null;

    const fvg=this.findFVG(ctx,forBuy,st.bos,disp.bar,liq.sw);
    if(fvg===null) return null;

    if(!this.locationOK(ctx,forBuy,st.pivot,(fvg.top+fvg.bottom)/2)) return null;

    const price=ctx.bars.close(1);
    const invalidation=forBuy?ctx.bars.low(liq.sw):ctx.bars.high(liq.sw);
    const atr=this.atr(ctx,1);
    if(!(atr>0)) return null;
    if(forBuy ? invalidation>=fvg.bottom : invalidation<=fvg.top) return null;

    const sweepQ=Math.max(0,Math.min(liq.ratio,1));
    const dispQ=Math.max(0,Math.min(disp.rangeATR/2.5,1));
    const structQ=Math.max(0,Math.min(st.strength,1));
    const fvgQ=Math.max(0,Math.min(fvg.widthATR,1));
    const freshQ=1;
    const locQ=1;
    const quality=forBuy
      ? 100*(0.20*sweepQ+0.20*dispQ+0.20*structQ+0.15*fvgQ+0.10*freshQ+0.15*locQ)
      : 100*(0.20*sweepQ+0.20*dispQ+0.20*structQ+0.15*fvgQ+0.10*freshQ+0.15*locQ);

    if(quality<ctx.inputs.minQuality) return null;
    if(ctx.inputs.rewardRisk<ctx.inputs.minRunnerRR)return null;
    if(!this.optionalFiltersOK(ctx,forBuy))return null;

    return {
      quality,
      sw:liq.sw,
      bos:st.bos,
      disp:disp.bar,
      fvg,
      invalidation,
      entryKey:(forBuy?"L":"S")+":"+st.bos+":"+fvg.completion,
      score:quality,
      rejectionRatio:liq.ratio,
      bosStrength:st.strength,
      sweepPenATR:liq.pen,
      sweepLevel:liq.pool,
      bosLevel:st.level,
      hasSweep:true,
      fvgDistanceATR:Math.abs(price-(fvg.top+fvg.bottom)/2)/atr
    };
  }


  finalizeDay(ctx:Context):void {
    if(this.dayKey<0||this.lastFinalizedDay===this.dayKey)return;
    if(this.currentDayEligible){
      this.daysObserved++;
      this.dailyEntrySum+=this.entriesToday;
      this.dailyShortfallSum+=Math.max(0,ctx.inputs.minDailyTrades-this.entriesToday);
      if(this.entriesToday>=ctx.inputs.minDailyTrades)this.daysMetMinimum++;
      else this.daysBelowMinimum++;
      if(this.entriesToday>this.maxEntriesInDay)this.maxEntriesInDay=this.entriesToday;
    }
    this.lastFinalizedDay=this.dayKey;
  }

  rollDay(ctx:Context):void {
    const key=Math.floor(ctx.time/86400000);
    const sessionNow=this.inSession(ctx);
    if(this.dayKey<0){
      this.dayKey=key;
      this.entriesToday=0;
      this.currentDayEligible=sessionNow;
      return;
    }
    if(key!==this.dayKey){
      this.finalizeDay(ctx);
      this.dayKey=key;
      this.entriesToday=0;
      this.currentDayEligible=sessionNow;
    }else if(sessionNow){
      this.currentDayEligible=true;
    }
  }

  tierIndex(tier:string):number {
    if(tier==="strict")return 0;
    if(tier==="singleSwing")return 1;
    if(tier==="continuation")return 2;
    if(tier==="microMomentum")return 3;
    return 4;
  }

  // Diagnostic only: lastClosedTrade exposes one latest close, so multiple closes on
  // one market update cannot be reconstructed here. Use saved session rows grouped by
  // openingFillId for authoritative whole-position and family/regime outcomes.
  // The StrategyTune API exposes only the latest close, not a complete close-event
  // stream. Count observer gaps for diagnostics, but never use this snapshot for
  // position P&L, win rate, or final attribution. Saved session rows are authoritative.
  captureLastClosed(ctx:Context):void {
    const engineClosedTrades=ctx.stats.trades;
    const newlyClosed=engineClosedTrades-this.lastEngineClosedTrades;
    if(newlyClosed>0)this.observedCloseUpdates++;
    if(newlyClosed>1)this.missedCloseEvents+=newlyClosed-1;
    this.lastEngineClosedTrades=engineClosedTrades;
  }

  // Position-level outcomes cannot be reconstructed safely from lastClosedTrade.
  // Finalization is retained only to retire local state; outcome metrics are joined
  // after the run from get_session_trades rows keyed by openingFillId.
  finalizePositionState(state:any,ctx:Context):void {
    if(state.finalized)return;
    state.finalized=true;
  }

  stateIndex(lotId:number):number {
    for(let i=0;i<this.tradeStates.length;i++)if(this.tradeStates[i].lotId===lotId)return i;
    return -1;
  }

  registerLot(ctx:Context,lot:any,risk:number):any {
    let idx=this.stateIndex(lot.lotId);
    if(idx>=0)return this.tradeStates[idx];
    const r=risk>0?risk:Math.abs(lot.entryPrice-(lot.stopLossPrice===null?lot.entryPrice:lot.stopLossPrice));
    const q:any={
      lotId:lot.lotId,
      side:lot.side,
      entryPrice:lot.entryPrice,
      risk:r>0?r:this.atr(ctx,1)*1.5,
      riskMoney:ctx.account.balance*ctx.inputs.riskFraction/100,
      entryTime:lot.entryTime,
      initialQuantity:lot.quantity,
      closedQty:0,
      closedRows:0,
      closedPnl:0,
      tp1Done:false,
      tp2Done:false,
      runnerTrailArmed:false,
      forceClosed:false,
      finalized:false,
      missingSince:0,
      tierIndex:3,
      featuresKnown:false,
      entryQuality:0, entryRVOL:0, spreadATR:0, rejectionRatio:0, fvgWidthATR:0,
      sweepAgeBars:0, bosAgeBars:0, displacementAgeBars:0, displacementRangeATR:0,
      displacementBodyRatio:0, trendSlopeATR:0, regimeProxy:-1,
      bosStrength:0, hasSweep:false, sweepGrade:0, sweepPenATR:0, sweepLevel:0, bosLevel:0,
      lateBeyondBosATR:0, sweepChaseATR:0, fvgDistanceATR:0, entryHourUTC:-1,
      maxFavorableR:0, maxAdverseR:0
    };
    this.tradeStates.push(q);
    return q;
  }

  manageLots(ctx:Context):void {
    this.captureLastClosed(ctx);
    const lots=ctx.account.lots;
    for(let i=0;i<lots.length;i++){
      const lot=lots[i];
      const st=this.registerLot(ctx,lot,0);
      if(!(st.risk>0)||st.forceClosed)continue;

      const isBuy=lot.side==="Long";
      const isSingleSwing=st.tierIndex===1;
      const isContinuation=st.tierIndex===2;
      const tp1RR=isSingleSwing?ctx.inputs.singleSwingTP1RR:(isContinuation?ctx.inputs.continuationTP1RR:ctx.inputs.tp1RR);
      const tp2RR=isSingleSwing?ctx.inputs.singleSwingTP2RR:(isContinuation?ctx.inputs.continuationTP2RR:ctx.inputs.tp2RR);
      const tp1CloseFraction=isSingleSwing?ctx.inputs.singleSwingTP1CloseFraction:(isContinuation?ctx.inputs.continuationTP1CloseFraction:ctx.inputs.tp1CloseFraction);
      const tp2CloseFraction=isSingleSwing?ctx.inputs.singleSwingTP2CloseFraction:(isContinuation?ctx.inputs.continuationTP2CloseFraction:ctx.inputs.tp2CloseFraction);
      const trailATR=isSingleSwing?ctx.inputs.singleSwingTrailATR:(isContinuation?ctx.inputs.continuationTrailATR:ctx.inputs.trailATR);
      const beOffsetR=isSingleSwing?ctx.inputs.singleSwingBEOffsetR:(isContinuation?ctx.inputs.continuationBEOffsetR:ctx.inputs.beOffsetR);
      const px=isBuy?ctx.bid:ctx.ask;
      const favorableR=isBuy?(px-st.entryPrice)/st.risk:(st.entryPrice-px)/st.risk;
      st.maxFavorableR=Math.max(st.maxFavorableR,favorableR);
      const adverseR=isBuy?(st.entryPrice-px)/st.risk:(px-st.entryPrice)/st.risk;
      st.maxAdverseR=Math.max(st.maxAdverseR,adverseR);
      // Keep excursion state in the durable primitive-string ledger as well as the
      // in-memory lot object; export does not depend on object-array identity at finish.
      for(let ri=0;ri<this.entryAttributionRecords.length;ri++){
        const telemetry=this.entryAttributionRecords[ri].split("|");
        if(telemetry.length>=22 && Number(telemetry[0])===lot.lotId){
          telemetry[20]=Math.max(Number(telemetry[20])||0,Math.max(0,adverseR)).toFixed(2);
          telemetry[21]=Math.max(Number(telemetry[21])||0,Math.max(0,favorableR)).toFixed(2);
          this.entryAttributionRecords[ri]=telemetry.join("|");
          break;
        }
      }
      const tp1=isBuy?st.entryPrice+st.risk*tp1RR:st.entryPrice-st.risk*tp1RR;
      const tp2=isBuy?st.entryPrice+st.risk*tp2RR:st.entryPrice-st.risk*tp2RR;
      const hit1=isBuy?px>=tp1:px<=tp1;
      const hit2=isBuy?px>=tp2:px<=tp2;

      if(!st.tp1Done&&hit1){
        const frac=Math.max(0,Math.min(tp1CloseFraction,0.95));
        if(frac>0)ctx.orders.closeLot(st.lotId,lot.quantity*frac);
        st.tp1Done=true;
        this.tp1Count++;

        // A partial close may consume the entire lot after the instrument's
        // minimum-volume/step rounding. Never modify stops on a lot that no
        // longer exists; this is especially important for small CFD volumes.
        const afterTP1Lots=ctx.account.lots;
        let afterTP1Qty=0;
        for(let j=0;j<afterTP1Lots.length;j++){
          if(afterTP1Lots[j].lotId===st.lotId)afterTP1Qty=afterTP1Lots[j].quantity;
        }
        if(afterTP1Qty>0){
          ctx.orders.setLotStops(st.lotId,{
            slPrice:isBuy?st.entryPrice+st.risk*beOffsetR:st.entryPrice-st.risk*beOffsetR,
            tpPrice:isBuy?st.entryPrice+st.risk*Math.max(ctx.inputs.rewardRisk,ctx.inputs.minRunnerRR):st.entryPrice-st.risk*Math.max(ctx.inputs.rewardRisk,ctx.inputs.minRunnerRR)
          });
        }else{
          st.forceClosed=true;
        }
      }else if(st.tp1Done&&!st.tp2Done&&hit2){
        const remain=Math.max(0.0001,1-tp1CloseFraction);
        const frac=Math.max(0,Math.min(tp2CloseFraction/remain,1));
        const liveLots=ctx.account.lots;
        let qty=0;
        for(let j=0;j<liveLots.length;j++)if(liveLots[j].lotId===st.lotId)qty=liveLots[j].quantity;
        if(qty>0&&frac>0)ctx.orders.closeLot(st.lotId,qty*frac);

        // The TP2 close is subject to the same volume-step behavior as TP1.
        // Only arm the runner if a residual lot still exists.
        const afterTP2Lots=ctx.account.lots;
        let afterTP2Qty=0;
        for(let j=0;j<afterTP2Lots.length;j++){
          if(afterTP2Lots[j].lotId===st.lotId)afterTP2Qty=afterTP2Lots[j].quantity;
        }
        if(afterTP2Qty>0){
          ctx.orders.setLotStops(st.lotId,{tpPrice:null});
          const a=this.atr(ctx,1);
          if(a>0)ctx.orders.setLotTrail(st.lotId,a*trailATR);
          st.runnerTrailArmed=true;
        }else{
          st.forceClosed=true;
        }
        st.tp2Done=true;
        this.tp2Count++;
      }

      if(!st.forceClosed&&st.entryTime>0&&ctx.time-st.entryTime>=ctx.inputs.maxHoldBars*ctx.run.interval*60000){
        ctx.orders.closeLot(st.lotId);
        st.forceClosed=true;
      }
    }

    // A second capture catches synchronous closes issued by this manager on the same update.
    this.captureLastClosed(ctx);
    const live=ctx.account.lots;
    for(let j=this.tradeStates.length-1;j>=0;j--){
      const state=this.tradeStates[j];
      let found=false;
      for(let i=0;i<live.length;i++)if(live[i].lotId===state.lotId){found=true;break;}
      if(found)state.missingSince=0;
      else if(state.missingSince===0)state.missingSince=ctx.time;
      else{
        this.finalizePositionState(state,ctx);
        this.tradeStates.splice(j,1);
      }
    }
  }

  selectDirection(buy:any,sell:any,directionalAdvantage:number):any {
    const buyOK=buy!==null,sellOK=sell!==null;
    if(!buyOK&&!sellOK)return null;
    if(buyOK&&!sellOK)return{side:"Long",chosen:buy};
    if(sellOK&&!buyOK)return{side:"Short",chosen:sell};
    const delta=buy.score-sell.score;
    if(delta>=directionalAdvantage)return{side:"Long",chosen:buy};
    if(-delta>=directionalAdvantage)return{side:"Short",chosen:sell};
    return null;
  }

  // Normalize each family score against its own configured entry floor before
  // comparing competing opportunities. This avoids giving one lane an automatic
  // priority merely because its raw quality formula runs on a different scale.
  laneCandidate(signal:any,tier:string,floor:number):any {
    if(signal===null)return null;
    const span=Math.max(1,100-floor);
    const rankScore=Math.max(0,Math.min(100,100*(signal.score-floor)/span));
    return{score:rankScore,tier,signal};
  }

  betterLaneCandidate(a:any,b:any):any {
    if(a===null)return b;
    if(b===null)return a;
    if(a.score>b.score)return a;
    if(b.score>a.score)return b;
    // Deterministic tie-break only; no lane receives unconditional priority.
    return a;
  }

  singleSwingChain(ctx:Context,forBuy:boolean):any {
    const atr=this.atr(ctx,1);
    if(!(atr>0)||ctx.bars.count<60)return null;
    let fastMean=0,slowMean=0;
    for(let k=1;k<=8;k++)fastMean+=ctx.bars.close(k);
    for(let k=1;k<=21;k++)slowMean+=ctx.bars.close(k);
    const trendSlopeATR=Math.abs(fastMean/8-slowMean/21)/atr;
    // In adaptive mode, preserve range-like entries for PD validation,
    // reject the weak transition band, and require stronger trend slope elsewhere.
    if(ctx.inputs.adaptiveFallbackPD && trendSlopeATR>=ctx.inputs.fallbackPDTrendThreshold &&
       trendSlopeATR<ctx.inputs.minSingleSwingTrendSlopeATR)return null;
    const maxPivot=Math.min(ctx.inputs.lookbackBars,45);
    const maxAge=Math.min(ctx.inputs.fallbackMaxSweepBars,ctx.inputs.maxSweepAgeBars+2);
    let best:any=null;

    for(let pivot=ctx.inputs.swingStrength+2;pivot<=maxPivot;pivot++){
      if(forBuy?!this.isSwingLow(ctx,pivot):!this.isSwingHigh(ctx,pivot))continue;
      const level=forBuy?ctx.bars.low(pivot):ctx.bars.high(pivot);
      for(let sw=pivot-1;sw>=Math.max(2,pivot-maxAge);sw--){
        // sw is the sweep bar's age in completed bars from the current signal bar.
        // Keep this separate from pivot-to-sweep age (fallbackMaxSweepBars).
        if(sw>ctx.inputs.maxFallbackSignalAgeBars)continue;
        const swept=forBuy
          ?ctx.bars.low(sw)<level&&ctx.bars.close(sw)>level
          :ctx.bars.high(sw)>level&&ctx.bars.close(sw)<level;
        if(!swept)continue;

        const wick=forBuy?level-ctx.bars.low(sw):ctx.bars.high(sw)-level;
        const reclaim=forBuy?ctx.bars.close(sw)-level:level-ctx.bars.close(sw);
        if(!(wick>0))continue;
        const rejection=Math.max(0,Math.min(1,reclaim/wick));
        if(rejection<ctx.inputs.minRejectionRatio*0.65)continue;

        let micro=forBuy?-Infinity:Infinity;
        for(let k=2;k<sw;k++){
          if(forBuy)micro=Math.max(micro,ctx.bars.high(k));
          else micro=Math.min(micro,ctx.bars.low(k));
        }
        if(!isFinite(micro))continue;
        const close1=ctx.bars.close(1),close2=ctx.bars.close(2);
        const crossed=forBuy
          ?close1>micro&&close2<=micro&&close1>ctx.bars.open(1)
          :close1<micro&&close2>=micro&&close1<ctx.bars.open(1);
        if(!crossed)continue;

        const body=this.bodyRatio(ctx,1);
        const range=ctx.bars.high(1)-ctx.bars.low(1);
        const rangeATR=range/atr;
        const effectiveRangeCap=ctx.inputs.adaptiveFallbackPD
          ? (trendSlopeATR<ctx.inputs.fallbackPDTrendThreshold?ctx.inputs.maxSingleSwingRangeATR:ctx.inputs.trendSingleSwingRangeATR)
          : ctx.inputs.maxSingleSwingRangeATR;
        if(body<ctx.inputs.minBodyRatio*0.75||rangeATR<0.55||rangeATR>effectiveRangeCap)continue;
        const breakQ=Math.max(0,Math.min(1,Math.abs(close1-micro)/(0.25*atr)));
        const rejectQ=Math.max(0,Math.min(1,rejection/0.65));
        const bodyQ=Math.max(0,Math.min(1,body/0.65));
        const quality=100*(0.35*rejectQ+0.40*breakQ+0.25*bodyQ);
        if(quality<ctx.inputs.singleSwingMinQuality)continue;

        let applyFallbackPD=ctx.inputs.requireFallbackPD;
        if(ctx.inputs.adaptiveFallbackPD){
          applyFallbackPD=trendSlopeATR<ctx.inputs.fallbackPDTrendThreshold;
        }
        if(applyFallbackPD){
          let rangeHigh=-Infinity,rangeLow=Infinity;
          const rangeLimit=Math.min(40,ctx.bars.count-2);
          for(let k=2;k<=rangeLimit;k++){
            rangeHigh=Math.max(rangeHigh,ctx.bars.high(k));
            rangeLow=Math.min(rangeLow,ctx.bars.low(k));
          }
          if(!(rangeHigh>rangeLow))continue;
          const midpoint=(rangeHigh+rangeLow)/2;
          const price=ctx.bars.close(1);
          if(forBuy?price>midpoint:price<midpoint)continue;
        }

        const invalidation=forBuy?ctx.bars.low(sw):ctx.bars.high(sw);
        const key="SS:"+(forBuy?"L":"S")+":"+ctx.bars.time(pivot)+":"+ctx.bars.time(sw);
        if(ctx.inputs.rewardRisk<ctx.inputs.minRunnerRR)continue;
        if(!this.optionalFiltersOK(ctx,forBuy))continue;
        const sweepATR=this.atr(ctx,sw);
        if(!(sweepATR>0))continue;
        const sweepPenATR=wick/sweepATR;
        // Mirror the production MQL5 v2.9 sweep grade: 40% close reclaim,
        // 30% penetration shape, 30% immediate displacement follow-through.
        const shapeScore=(sweepPenATR>=0.03&&sweepPenATR<=0.60)
          ?1:Math.max(0,1-Math.abs(sweepPenATR-0.30)/0.60);
        const followIdx=sw-1;
        let followThrough=false;
        if(followIdx>=1){
          const followATR=this.atr(ctx,followIdx);
          const followRange=ctx.bars.high(followIdx)-ctx.bars.low(followIdx);
          const followDirectional=forBuy
            ?ctx.bars.close(followIdx)>ctx.bars.open(followIdx)
            :ctx.bars.close(followIdx)<ctx.bars.open(followIdx);
          const followBody=followRange>0
            ?Math.abs(ctx.bars.close(followIdx)-ctx.bars.open(followIdx))/followRange:0;
          const oppositeWick=forBuy
            ?ctx.bars.open(followIdx)-ctx.bars.low(followIdx)
            :ctx.bars.high(followIdx)-ctx.bars.open(followIdx);
          followThrough=followDirectional&&followATR>0&&followRange/followATR>=1.2
            &&followBody>=0.6&&oppositeWick<=0.3*followRange;
        }
        const sweepGradeScore=Math.max(0,Math.min(0.4*rejection+0.3*shapeScore+0.3*(followThrough?1:0),1));
        const sweepGrade=sweepGradeScore>=0.70?3:(sweepGradeScore>=0.40?2:1);
        // Mirror production BOSStrength: 60% distance (full at 0.5 ATR),
        // 40% confirming candle body dominance.
        const bosBreak=forBuy?close1-micro:micro-close1;
        const bosDistScore=Math.max(0,Math.min(bosBreak/(0.5*atr),1));
        const bosStrength=Math.max(0,Math.min(0.6*bosDistScore+0.4*body,1));
        const cand={quality,score:quality,sw,bos:1,disp:1,invalidation,entryKey:key,
          rejectionRatio:rejection,mode:"singleSwing",bosStrength,sweepPenATR,
          sweepLevel:level,bosLevel:close1,sweepGrade,hasSweep:true,fvgDistanceATR:0};
        if(best===null||cand.score>best.score)best=cand;
      }
    }
    return best;
  }

  continuationChain(ctx:Context,forBuy:boolean):any {
    const atr=this.atr(ctx,1);
    if(!(atr>0)||ctx.bars.count<60)return null;
    let fast=0,slow=0;
    for(let i=1;i<=20;i++)fast+=ctx.bars.close(i);
    for(let i=1;i<=50;i++)slow+=ctx.bars.close(i);
    fast/=20; slow/=50;
    const close1=ctx.bars.close(1),close2=ctx.bars.close(2);
    if(forBuy?!(close1>fast&&fast>slow):!(close1<fast&&fast<slow))return null;

    const body=this.bodyRatio(ctx,1);
    const range=ctx.bars.high(1)-ctx.bars.low(1);
    // Frequency-preserving continuation expansion: retain the EMA trend
    // alignment and confirmed break, but admit slightly less extreme impulse bars
    // and look for a pullback touch across a modestly wider recent window.
    if(body<0.35||range/atr<0.45)return null;

    let touched=false;
    for(let i=1;i<=8;i++){
      if(forBuy){
        if(ctx.bars.low(i)<=fast+0.20*atr&&ctx.bars.high(i)>=fast-0.20*atr)touched=true;
      }else{
        if(ctx.bars.high(i)>=fast-0.20*atr&&ctx.bars.low(i)<=fast+0.20*atr)touched=true;
      }
    }
    if(!touched)return null;

    let level=forBuy?-Infinity:Infinity;
    for(let i=2;i<=5;i++){
      if(forBuy)level=Math.max(level,ctx.bars.high(i));
      else level=Math.min(level,ctx.bars.low(i));
    }
    const crossed=forBuy?close1>level&&close2<=level:close1<level&&close2>=level;
    if(!crossed)return null;

    const strength=Math.max(0,Math.min(1,Math.abs(close1-level)/(0.25*atr)));
    const quality=100*(0.45*Math.min(body/0.7,1)+0.35*strength+0.20*Math.min(Math.abs(close1-fast)/atr,1));
    if(quality<ctx.inputs.fallbackQualityFloor)return null;
    if(ctx.inputs.rewardRisk<ctx.inputs.minRunnerRR)return null;
    if(!this.optionalFiltersOK(ctx,forBuy))return null;

    let invalidation=forBuy?ctx.bars.low(1):ctx.bars.high(1);
    for(let i=2;i<=5;i++)invalidation=forBuy?Math.min(invalidation,ctx.bars.low(i)):Math.max(invalidation,ctx.bars.high(i));
    const key="TC:"+(forBuy?"L":"S")+":"+ctx.bars.time(1)+":"+this.priceKey(ctx,level);
    return{quality,score:quality,sw:1,bos:1,disp:1,invalidation,entryKey:key,rejectionRatio:body,mode:"continuation",bosStrength:strength,bosLevel:level,sweepPenATR:0,sweepLevel:0,hasSweep:false,fvgDistanceATR:0};
  }

  microMomentumChain(ctx:Context,forBuy:boolean):any {
    const atr=this.atr(ctx,1);
    if(!(atr>0)||ctx.bars.count<60)return null;

    let fast=0,slow=0;
    for(let i=1;i<=9;i++)fast+=ctx.bars.close(i);
    for(let i=1;i<=20;i++)slow+=ctx.bars.close(i);
    fast/=9; slow/=20;

    const close1=ctx.bars.close(1),close2=ctx.bars.close(2);
    if(forBuy?!(close1>fast&&fast>slow):!(close1<fast&&fast<slow))return null;

    const body=this.bodyRatio(ctx,1);
    const range=ctx.bars.high(1)-ctx.bars.low(1);
    if(body<0.30||range/atr<0.45)return null;

    let level=forBuy?-Infinity:Infinity;
    for(let i=2;i<=4;i++){
      if(forBuy)level=Math.max(level,ctx.bars.high(i));
      else level=Math.min(level,ctx.bars.low(i));
    }
    const crossed=forBuy?close1>level&&close2<=level:close1<level&&close2>=level;
    if(!crossed)return null;

    let pullback=false;
    for(let i=1;i<=6;i++){
      if(forBuy){
        if(ctx.bars.low(i)<=fast+0.35*atr&&ctx.bars.high(i)>=fast-0.35*atr)pullback=true;
      }else{
        if(ctx.bars.high(i)>=fast-0.35*atr&&ctx.bars.low(i)<=fast+0.35*atr)pullback=true;
      }
    }
    if(!pullback)return null;

    const bodyQ=Math.max(0,Math.min(1,body/0.65));
    const breakQ=Math.max(0,Math.min(1,Math.abs(close1-level)/(0.20*atr)));
    const trendQ=Math.max(0,Math.min(1,Math.abs(fast-slow)/(0.40*atr)));
    const quality=100*(0.35*bodyQ+0.45*breakQ+0.20*trendQ);
    if(quality<ctx.inputs.microMomentumMinQuality)return null;
    if(ctx.inputs.rewardRisk<ctx.inputs.minRunnerRR)return null;
    if(!this.optionalFiltersOK(ctx,forBuy))return null;

    let invalidation=forBuy?ctx.bars.low(1):ctx.bars.high(1);
    for(let i=2;i<=4;i++)invalidation=forBuy?Math.min(invalidation,ctx.bars.low(i)):Math.max(invalidation,ctx.bars.high(i));
    const key="MM:"+(forBuy?"L":"S")+":"+ctx.bars.time(1)+":"+this.priceKey(ctx,level);
    return{quality,score:quality,sw:1,bos:1,disp:1,invalidation,entryKey:key,rejectionRatio:body,mode:"microMomentum"};
  }

  onUpdate(ctx:Context):void {
    this.rollDay(ctx);
    if(this.applyWeekendGuard(ctx))return;
    if(ctx.bars.count<100)return;

    // Manage every open lot independently. Entries may be added in the same net direction,
    // so long runners do not block all new same-direction opportunities.
    this.manageLots(ctx);

    if(!ctx.isNewBar||!this.inSession(ctx))return;

    if(this.entriesToday>=ctx.inputs.maxDailyTrades)return;

    const atr=this.atr(ctx,1);
    if(!(atr>0))return;

    const currentDirection:TradeSide|null=ctx.account.position>0?"Long":(ctx.account.position<0?"Short":null);
    const buy=(!ctx.inputs.enableLongs||(!ctx.inputs.enableStrictFamily||currentDirection==="Short"))?null:this.chain(ctx,true);
    const sell=(!ctx.inputs.enableShorts||(!ctx.inputs.enableStrictFamily||currentDirection==="Long"))?null:this.chain(ctx,false);
    let selected=this.selectDirection(buy,sell,ctx.inputs.directionalAdvantage);
    let tier="strict";

    // Strict-family entries remain an explicitly disabled-by-default legacy lane.
    // The continuation lane has first priority to preserve its standalone decisions.
    // Fresh single-swing entries are additive only when neither continuation side
    // produces a candidate on this bar; this avoids cross-lane replacement/duplication.
    if(selected===null){
      const sb=ctx.inputs.enableLongs&&ctx.inputs.enableSingleSwingFallback&&currentDirection!=="Short"
        ?this.singleSwingChain(ctx,true):null;
      const ss=ctx.inputs.enableShorts&&ctx.inputs.enableSingleSwingFallback&&currentDirection!=="Long"
        ?this.singleSwingChain(ctx,false):null;
      const cb=ctx.inputs.enableLongs&&ctx.inputs.enableContinuationFallback&&currentDirection!=="Short"
        ?this.continuationChain(ctx,true):null;
      const cs=ctx.inputs.enableShorts&&ctx.inputs.enableContinuationFallback&&currentDirection!=="Long"
        ?this.continuationChain(ctx,false):null;

      if(sb!==null)this.dualLaneSingleSwingCandidates++;
      if(ss!==null)this.dualLaneSingleSwingCandidates++;
      if(cb!==null)this.dualLaneContinuationCandidates++;
      if(cs!==null)this.dualLaneContinuationCandidates++;
      if((sb!==null||ss!==null)&&(cb!==null||cs!==null))this.dualLaneCompetitionBars++;

      const sbRank=this.laneCandidate(sb,"singleSwing",ctx.inputs.singleSwingMinQuality);
      const ssRank=this.laneCandidate(ss,"singleSwing",ctx.inputs.singleSwingMinQuality);
      const cbRank=this.laneCandidate(cb,"continuation",ctx.inputs.fallbackQualityFloor);
      const csRank=this.laneCandidate(cs,"continuation",ctx.inputs.fallbackQualityFloor);

      // Keep the original lane normalization and direction-advantage semantics.
      const continuationSelected=(cbRank!==null||csRank!==null)
        ?this.selectDirection(cbRank,csRank,ctx.inputs.directionalAdvantage):null;
      if(continuationSelected!==null){
        selected=continuationSelected;
        tier="continuation";
      }else{
        selected=this.selectDirection(sbRank,ssRank,ctx.inputs.directionalAdvantage);
        if(selected!==null)tier="singleSwing";
      }
    }

    // Micro-momentum remains disabled by default and is only consulted when neither
    // of the two combined lanes produces an admissible candidate.
    if(selected===null&&ctx.inputs.enableMicroMomentumFallback){
      const mb=!ctx.inputs.enableLongs||currentDirection==="Short"?null:this.microMomentumChain(ctx,true);
      const ms=!ctx.inputs.enableShorts||currentDirection==="Long"?null:this.microMomentumChain(ctx,false);
      selected=this.selectDirection(mb,ms,ctx.inputs.directionalAdvantage);
      if(selected!==null)tier="microMomentum";
    }
    if(selected===null)return;

    if(tier==="singleSwing")this.dualLaneSingleSwingSelections++;
    if(tier==="continuation")this.dualLaneContinuationSelections++;
    const side:TradeSide=selected.side;
    const chosen=tier==="singleSwing"||tier==="continuation"
      ?selected.chosen.signal:selected.chosen;

    // Optional family-specific eligibility gate. The transition band is excluded
    // from both specialist lanes when these switches are enabled.
    const entryRegimeSlopeATR=this.trendSlopeProxyATR(ctx);
    if(tier==="singleSwing" && ctx.inputs.rangeOnlySingleSwing &&
       (!isFinite(entryRegimeSlopeATR)||entryRegimeSlopeATR>=ctx.inputs.rangeRegimeMaxSlopeATR)){
      this.blockedSingleSwingRegime++;
      return;
    }

    // Gold research hybrid: single-swing is eligible only in trend-like conditions.
    if(tier==="singleSwing" && ctx.inputs.trendOnlySingleSwing &&
       (!isFinite(entryRegimeSlopeATR)||entryRegimeSlopeATR<ctx.inputs.trendRegimeMinSlopeATR)){
      this.blockedSingleSwingRegime++;
      return;
    }
    if(tier==="continuation" && ctx.inputs.trendOnlyContinuation &&
       (!isFinite(entryRegimeSlopeATR)||entryRegimeSlopeATR<ctx.inputs.trendRegimeMinSlopeATR)){
      this.blockedContinuationRegime++;
      return;
    }

    // Gold research ablation: continuation is eligible only in the transition band.
    // Range-like and trend-like conditions are rejected; thresholds remain inputs.
    if(tier==="continuation" && ctx.inputs.transitionOnlyContinuation &&
       (!isFinite(entryRegimeSlopeATR) ||
        entryRegimeSlopeATR<ctx.inputs.rangeRegimeMaxSlopeATR ||
        entryRegimeSlopeATR>=ctx.inputs.trendRegimeMinSlopeATR)){
      this.blockedContinuationRegime++;
      return;
    }

    // Netting-account safety: only add in the existing net direction until it is flat.
    if(ctx.account.position>0&&side!=="Long"){this.blockedOpposite++;return;}
    if(ctx.account.position<0&&side!=="Short"){this.blockedOpposite++;return;}

    const liveLots=ctx.account.lots;
    if(liveLots.length>=ctx.inputs.maxConcurrentLots){this.blockedConcurrency++;return;}
    const riskPercent=tier==="strict"?ctx.inputs.riskFraction:ctx.inputs.opportunityRiskFraction;
    if(!(riskPercent>0))return;
    const currentOpenRisk=this.openRiskPercent(ctx);
    const projectedOpenRisk=currentOpenRisk+riskPercent;
    if(!isFinite(currentOpenRisk)||projectedOpenRisk>ctx.inputs.maxPortfolioRiskPercent){
      this.blockedRiskCap++;
      return;
    }

    if(chosen.entryKey===this.lastKey)return;
    if(this.lastEntryTime>0&&ctx.time-this.lastEntryTime<ctx.inputs.cooldownBars*ctx.run.interval*60000)return;

    // Validate the protective stop against the executable side of the current quote, not the prior closed bar.
    const entryReference=side==="Long"?ctx.ask:ctx.bid;
    const familyStopBufferATR=tier==="singleSwing"?ctx.inputs.singleSwingStopBufferATR:
      (tier==="continuation"?ctx.inputs.continuationStopBufferATR:ctx.inputs.stopBufferATR);
    const familyMaxStopATR=tier==="singleSwing"?ctx.inputs.singleSwingMaxStopATR:
      (tier==="continuation"?ctx.inputs.continuationMaxStopATR:4.0);
    const stopPrice=side==="Long"
      ?chosen.invalidation-familyStopBufferATR*atr
      :chosen.invalidation+familyStopBufferATR*atr;
    const slDist=side==="Long"?entryReference-stopPrice:stopPrice-entryReference;
    if(!(slDist>0)||slDist/atr>familyMaxStopATR){this.blockedStops++;return;}

    let fill:any;
    try {
      fill=ctx.orders.marketOrder({
        side,
        risk:{percent:riskPercent},
        slPrice:stopPrice
      });
    } catch (e:any) {
      // Research-only fail-safe: skip entries the engine rejects, including sizes below its minimum step.
      this.blockedSizing++;
      return;
    }
    if(fill.lotIds.length===0)return;

    this.lastKey=chosen.entryKey;
    this.lastEntryTime=ctx.time;
    this.entryTime=ctx.time;
    this.activeLotId=fill.lotIds[0];
    this.tradeRisk=slDist;

    // Capture only information available at the signal/entry bar. This block does not
    // participate in selection, sizing, order placement or exits.
    const featureATR=this.atr(ctx,1);
    const spreadATR=featureATR>0?Math.max(0,ctx.ask-ctx.bid)/featureATR:0;
    const entryRVOL=this.rvol(ctx);
    const sweepAgeBars=chosen.sw;
    const bosAgeBars=chosen.bos;
    const displacementAgeBars=chosen.disp;
    const displacementATR=this.atr(ctx,chosen.disp);
    const displacementRangeATR=displacementATR>0?(ctx.bars.high(chosen.disp)-ctx.bars.low(chosen.disp))/displacementATR:0;
    const displacementRange=ctx.bars.high(chosen.disp)-ctx.bars.low(chosen.disp);
    const displacementBodyRatio=displacementRange>0?Math.abs(ctx.bars.close(chosen.disp)-ctx.bars.open(chosen.disp))/displacementRange:0;
    let fastMean=0,slowMean=0;
    for(let k=1;k<=8;k++)fastMean+=ctx.bars.close(k);
    for(let k=1;k<=21;k++)slowMean+=ctx.bars.close(k);
    fastMean/=8; slowMean/=21;
    const trendSlopeATR=featureATR>0?Math.abs(fastMean-slowMean)/featureATR:0;
    // Research-only regime proxy: 0=range-like, 1=transition, 2=trend-like.
    // It is not claimed to reproduce the MT5 EA's trend/phase classifier.
    const regimeProxy=trendSlopeATR>=0.45?2:(trendSlopeATR<0.20?0:1);
    const entryFVGWidthATR=chosen.fvg!==undefined?chosen.fvg.widthATR:0;
    const hasSweep=chosen.hasSweep===true;
    const sweepPenATR=hasSweep&&typeof chosen.sweepPenATR==="number"?chosen.sweepPenATR:0;
    const bosStrength=typeof chosen.bosStrength==="number"?chosen.bosStrength:0;
    // Research proxy only: A/B/C bands use sweep reclaim ratio, not the production grade.
    const sweepGrade=hasSweep&&typeof chosen.sweepGrade==="number"?chosen.sweepGrade:0;
    const bosLevel=typeof chosen.bosLevel==="number"?chosen.bosLevel:fill.fillPrice;
    const sweepLevel=hasSweep&&typeof chosen.sweepLevel==="number"?chosen.sweepLevel:0;
    const lateBeyondBosATR=side==="Long"?(fill.fillPrice-bosLevel)/Math.max(featureATR,1e-9):(bosLevel-fill.fillPrice)/Math.max(featureATR,1e-9);
    const sweepChaseATR=hasSweep?(side==="Long"?(fill.fillPrice-sweepLevel)/Math.max(featureATR,1e-9):(sweepLevel-fill.fillPrice)/Math.max(featureATR,1e-9)):0;
    const fvgDistanceATR=chosen.fvg!==undefined?Math.abs(fill.fillPrice-(chosen.fvg.top+chosen.fvg.bottom)/2)/Math.max(featureATR,1e-9):0;
    const entryHourUTC=new Date(ctx.time).getUTCHours();

    for(let i=0;i<fill.lotIds.length;i++){
      let initialQty=0;
      const openedLots=ctx.account.lots;
      for(let j=0;j<openedLots.length;j++)if(openedLots[j].lotId===fill.lotIds[i])initialQty=openedLots[j].quantity;
      this.tradeStates.push({
        lotId:fill.lotIds[i],
        side,
        entryPrice:fill.fillPrice,
        risk:slDist,
        riskMoney:ctx.account.balance*riskPercent/100,
        entryTime:ctx.time,
        initialQuantity:initialQty,
        closedQty:0,
        closedRows:0,
        closedPnl:0,
        tp1Done:false,
        tp2Done:false,
        runnerTrailArmed:false,
        forceClosed:false,
        finalized:false,
        missingSince:0,
        tierIndex:this.tierIndex(tier),
        featuresKnown:true,
        entryQuality:chosen.quality,
        entryRVOL,
        spreadATR,
        rejectionRatio:chosen.rejectionRatio,
        fvgWidthATR:entryFVGWidthATR,
        sweepAgeBars,
        bosAgeBars,
        displacementAgeBars,
        displacementRangeATR,
        displacementBodyRatio,
        trendSlopeATR,
        regimeProxy,
        bosStrength,
        hasSweep,
        sweepGrade,
        sweepPenATR,
        sweepLevel,
        bosLevel,
        lateBeyondBosATR,
        sweepChaseATR,
        fvgDistanceATR,
        entryHourUTC,
        maxFavorableR:0,
        maxAdverseR:0
      });
      // Persist entry-time lineage independently of the in-run close observer.
      // Saved session rows are joined later by the exact openingFillId / lotId key.
      // Compact, lossless join record: timestamps are UTC seconds and all
      // price fields retain the active instrument's native decimal precision.
      // Sweep-specific diagnostics remain in memory; this export carries the
      // fields needed for robust session-row joins and core performance slicing.
      const entryRecord=[
        String(fill.lotIds[i]),
        String(Math.floor(ctx.time/1000)),
        side==="Long"?"L":"S",
        this.priceKey(ctx,fill.fillPrice),
        this.priceKey(ctx,slDist),
        String(this.tierIndex(tier)),
        String(regimeProxy),
        chosen.quality.toFixed(1),
        hasSweep?"1":"0",
        String(entryHourUTC),
        "0.00",
        "0.00"
      ].join("|");
      this.entryAttributionRecords.push(entryRecord);
    }

    this.entriesToday++;
    this.totalEntriesPlaced++;
    if(this.entriesToday>this.maxEntriesInDay)this.maxEntriesInDay=this.entriesToday;
    if(tier==="strict")this.strictEntries++;
    else if(tier==="singleSwing")this.singleSwingEntries++;
    else if(tier==="continuation")this.continuationEntries++;
    else if(tier==="microMomentum")this.microMomentumEntries++;
    else this.continuationEntries++;

  }

  onFinish(ctx:Context):void {
    this.captureLastClosed(ctx);
    this.finalizeDay(ctx);
    const liveAtFinish=ctx.account.lots;
    for(let i=0;i<this.tradeStates.length;i++){
      let isOpen=false;
      for(let j=0;j<liveAtFinish.length;j++){
        if(liveAtFinish[j].lotId===this.tradeStates[i].lotId){isOpen=true;break;}
      }
      if(!isOpen)this.finalizePositionState(this.tradeStates[i],ctx);
    }

    const engineClosedTradeRows=ctx.stats.trades;
    const closeObserverComplete=(this.missedCloseEvents===0 &&
                                 this.observedCloseUpdates===engineClosedTradeRows);

    // This is ENTRY-TIME feature telemetry only. Session close rows, grouped by
    // openingFillId, are the only accepted source for realized position outcomes.
    const positionRecords=this.entryAttributionRecords.slice();
    const mapChunks:string[]=[];
    let mapChunk="";
    const expectedPriceDigits=this.pricePrecision(ctx);
    const seenLotIds:string[]=[];
    let malformedEntryRecords=0;
    let duplicateEntryLotIds=0;
    let invalidPricePrecisionRecords=0;
    for(let ri=0;ri<positionRecords.length;ri++){
      const fields=positionRecords[ri].split("|");
      if(fields.length!==12 || !/^\d+$/.test(fields[0]) || !/^\d+$/.test(fields[1])){
        malformedEntryRecords++;
        continue;
      }
      if(seenLotIds.indexOf(fields[0])>=0)duplicateEntryLotIds++;
      else seenLotIds.push(fields[0]);
      const priceDecimals=fields[3].indexOf(".")>=0?fields[3].length-fields[3].indexOf(".")-1:0;
      const riskDecimals=fields[4].indexOf(".")>=0?fields[4].length-fields[4].indexOf(".")-1:0;
      if(priceDecimals!==expectedPriceDigits || riskDecimals!==expectedPriceDigits)invalidPricePrecisionRecords++;
    }
    for(let i=0;i<positionRecords.length;i++){
      const record=positionRecords[i];
      const candidate=mapChunk.length>0?mapChunk+";"+record:record;
      if(candidate.length>235 && mapChunk.length>0){
        mapChunks.push(mapChunk);
        mapChunk=record;
      }else{
        mapChunk=candidate;
      }
    }
    if(mapChunk.length>0)mapChunks.push(mapChunk);
    const maxMapChunks=80;
    const exportedChunks=Math.min(mapChunks.length,maxMapChunks);
    for(let i=0;i<exportedChunks;i++){
      ctx.stats.custom.set("entryMap"+i,mapChunks[i]);
    }
    ctx.stats.custom.set("entryMapVersion",5);
    ctx.stats.custom.set("entryMapRecords",positionRecords.length);
    ctx.stats.custom.set("entryMapExportedRecords",mapChunks.slice(0,exportedChunks).reduce((n,x)=>n+(x.length?x.split(";").length:0),0));
    ctx.stats.custom.set("entryMapTruncatedRecords",Math.max(0,positionRecords.length-mapChunks.slice(0,exportedChunks).reduce((n,x)=>n+(x.length?x.split(";").length:0),0)));
    ctx.stats.custom.set("entryMapPriceDigits",this.pricePrecision(ctx));
    ctx.stats.custom.set("entryMapMalformedRecords",malformedEntryRecords);
    ctx.stats.custom.set("entryMapDuplicateLotIds",duplicateEntryLotIds);
    ctx.stats.custom.set("entryMapInvalidPricePrecisionRecords",invalidPricePrecisionRecords);
    ctx.stats.custom.set("entryMapIntegrityValid",malformedEntryRecords===0 && duplicateEntryLotIds===0 && invalidPricePrecisionRecords===0 && positionRecords.length===mapChunks.slice(0,exportedChunks).reduce((n,x)=>n+(x.length?x.split(";").length:0),0));
    ctx.stats.custom.set("entryMapChunks",mapChunks.length);
    ctx.stats.custom.set("entryMapOverflow",mapChunks.length>maxMapChunks);
    ctx.stats.custom.set("entryMapSchema","lotId|tsUTCSeconds|side|price|risk|family|regime|quality|hasSweep|UTC_hour|MAE_R|MFE_R");
    ctx.stats.custom.set("entryMapTimeUnit","unix_utc_seconds");
    ctx.stats.custom.set("entryMapLotIdSemantics","opening_lot_id_matches_session_openingFillId");
    ctx.stats.custom.set("entryMapOutcomeJoinKey","openingFillId");
    ctx.stats.custom.set("positionAttributionValid",false);
    ctx.stats.custom.set("positionAttributionSource","saved_session_rows_by_openingFillId");
    ctx.stats.custom.set("sessionRowsRequired",true);
    ctx.stats.custom.set("positionOutcomeStatsSuppressed",true);
    ctx.stats.custom.set("engineClosedTradeRows",engineClosedTradeRows);
    ctx.stats.custom.set("inRunCloseObserverUpdates",this.observedCloseUpdates);
    ctx.stats.custom.set("inRunCloseObserverMissingEvents",this.missedCloseEvents);
    ctx.stats.custom.set("closeObserverUnobservableCloseEvents",this.missedCloseEvents);
    ctx.stats.custom.set("closeObserverMode","latest_close_snapshot_not_event_stream");
    ctx.stats.custom.set("closeObserverIsAuthoritative",false);
    ctx.stats.custom.set("inRunCloseObserverLooksComplete",closeObserverComplete);
    ctx.stats.custom.set("entriesOpenAtEnd",ctx.account.lots.length);
  }
}
export default MidasTouch2NoQuotaResearch;
