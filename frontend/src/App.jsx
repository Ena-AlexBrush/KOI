import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, ArrowUpRight, CalendarDays, Check, ChevronDown, CircleAlert, Clock3, Link2, MapPin, Plane, Search, Sparkles, TrainFront, Users, Wallet, X } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const agentInfo = {
  Travel: { icon: Plane, color: 'blue', role: 'Flight status and replacement flights' },
  Budget: { icon: Wallet, color: 'coral', role: 'Fares and lower-cost options' },
  Commitments: { icon: CalendarDays, color: 'violet', role: 'Arrival deadline and important plans' },
  Alternatives: { icon: TrainFront, color: 'green', role: 'Bus, train, ferry, and alternate airports' },
};

function localDate(){const now=new Date();const local=new Date(now.getTime()-now.getTimezoneOffset()*60000);return local.toISOString().slice(0,10)}
function prettyDate(value){if(!value)return '';return new Date(`${value}T12:00:00`).toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric',year:'numeric'})}
function groupByRound(responses){const groups=new Map();for(const response of responses||[]){const items=groups.get(response.round_number)||[];items.push(response);groups.set(response.round_number,items)}return [...groups.entries()].sort((a,b)=>a[0]-b[0])}
function priceAmount(value){const match=String(value||'').replaceAll(',','').match(/\$?\s*(\d+(?:\.\d+)?)/);return match?Number(match[1]):null}
function googleFlightsSearchUrl(trip){return `https://www.google.com/travel/flights?q=${encodeURIComponent(`Flights from ${trip.origin} to ${trip.destination} on ${trip.travel_date}`)}`}
function googleSearchUrl(trip){return `https://www.google.com/search?q=${encodeURIComponent(`${trip.origin} to ${trip.destination} flights bus train ${trip.travel_date}`)}`}

export default function App(){
  const [form,setForm]=useState({flight_number:'',airline:'',origin:'',destination:'',travel_date:localDate(),budget_usd:'300',arrive_by:'',important_plans:''});
  const [run,setRun]=useState(null),[config,setConfig]=useState(null),[busy,setBusy]=useState(false),[connection,setConnection]=useState('disconnected'),[message,setMessage]=useState('');
  const [agentProgress,setAgentProgress]=useState({}),[selectedOptionIndex,setSelectedOptionIndex]=useState(0),[acceptedOption,setAcceptedOption]=useState(null),[noOptionsLeft,setNoOptionsLeft]=useState(false);
  const stream=useRef(null);
  const responses=run?.responses||[];
  const rounds=useMemo(()=>groupByRound(responses),[responses]);
  const sources=run?.web_sources||[];

  useEffect(()=>{fetch(`${API}/api/config`).then(r=>r.json()).then(setConfig).catch(()=>setConfig({offline:true}));return()=>stream.current?.close()},[]);
  useEffect(()=>{if(run?.status!=='research_complete')return;const frame=requestAnimationFrame(()=>document.getElementById('decision')?.scrollIntoView({behavior:'smooth',block:'start'}));return()=>cancelAnimationFrame(frame)},[run?.status]);
  function updateField(event){setForm(current=>({...current,[event.target.name]:event.target.value}))}
  function connect(runId){
    stream.current?.close();setConnection('connecting');
    const streamConnection=new EventSource(`${API}/api/runs/${runId}/events?after=0`);stream.current=streamConnection;
    streamConnection.onopen=()=>setConnection('connected');streamConnection.onerror=()=>setConnection('disconnected');
    streamConnection.onmessage=async event=>{
      try{
        const item=JSON.parse(event.data),data=item.data||{};
        setRun(current=>{
          if(!current)return current;
          if(item.type==='agent_response')return {...current,responses:[...(current.responses||[]),data]};
          if(item.type==='web_research_completed'){
            const known=new Set((current.web_sources||[]).map(source=>source.source_id));
            const found=(data.sources||[]).filter(source=>!known.has(source.source_id));
            return {...current,web_sources:[...(current.web_sources||[]),...found]};
          }
          if(item.type==='run_error')return {...current,status:'error',error:data.message};
          if(item.type==='run_completed')return {...current,status:data.status,elapsed_ms:data.elapsed_ms};
          return current;
        });
        if(item.type==='web_search_started')setAgentProgress(Object.fromEntries((data.agents||[]).map(name=>[name,'Searching the web'])));
        if(item.type==='web_research_completed')setAgentProgress(current=>({...current,[data.agent]:data.error?'Search failed':`${data.source_count||0} sources found`}));
        if(item.type==='round_started')setMessage(item.data.round_number===0?'Agents are reviewing their web findings.':'Agents are comparing findings and responding to one another.');
        if(item.type==='run_error')setMessage(data.message||'The live search did not complete.');
        if(item.type==='run_completed'){
          streamConnection.close();
          let completedRun=null;
          try{const result=await fetch(`${API}/api/runs/${runId}`);if(result.ok){completedRun=await result.json();setRun(completedRun)}}catch{}
          setBusy(false);setConnection('complete');
          setMessage(completedRun?.limited_mode?'Ollama did not finish; KOI is showing cited live search results. Verify details with the airline or operator.':data.status==='research_complete'?'Research complete. Confirm schedules and fares with the linked operators.':data.message||'Run finished.');
        }
      }catch{}
    };
  }
  async function startResearch(event){
    event.preventDefault();setBusy(true);setMessage('Preparing live web research…');setRun(null);setAgentProgress({});setSelectedOptionIndex(0);setAcceptedOption(null);setNoOptionsLeft(false);stream.current?.close();
    const tripDetails={
      flight_number:form.flight_number.trim(),airline:form.airline.trim(),origin:form.origin.trim(),destination:form.destination.trim(),
      travel_date:form.travel_date,budget_usd:Number(form.budget_usd),arrive_by:form.arrive_by||null,
      important_plans:form.important_plans.split('\n').map(line=>line.trim()).filter(Boolean),
    };
    try{
      const response=await fetch(`${API}/api/runs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'live',trip_details:tripDetails})});
      if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||`Request failed (${response.status})`)}
      const value=await response.json();setRun(value);connect(value.run_id);setMessage('Live web searches are starting.');
      document.getElementById('research')?.scrollIntoView({behavior:'smooth',block:'start'});
    }catch(error){setBusy(false);setMessage(`Could not start research: ${error.message}`)}
  }
  function jumpTo(id){const target=document.getElementById(id);if(target?.tagName==='DETAILS')target.open=true;if(id==='research'){const disclosure=target?.querySelector('.research-disclosure');if(disclosure)disclosure.open=true}target?.scrollIntoView({behavior:'smooth',block:'start'})}
  const latestResponses=responses.filter(item=>item.round_number===(rounds.at(-1)?.[0]??-1));
  const allFindings=latestResponses.flatMap(response=>(response.findings||[]).map(finding=>({...finding,agent_name:response.agent_name})));
  const visibleFindings=allFindings.slice(0,3);
  const additionalFindings=allFindings.slice(3);
  const rankedOptions=useMemo(()=>{
    const unique=[];const seen=new Set();
    for(const finding of allFindings){if(!finding.source_ids?.length)continue;const key=`${finding.title}|${finding.transport_mode}`.toLowerCase();if(!seen.has(key)){seen.add(key);unique.push(finding)}}
    const budget=Number(run?.trip_details?.budget_usd);
    return unique.sort((a,b)=>{
      const score=item=>{const amount=priceAmount(item.price);return (item.booking_source_id?25:0)+(item.source_ids?.length?20:0)+(amount!==null?(amount<=budget?50:-50):0)+(item.arrival?5:0)};
      return score(b)-score(a)||(priceAmount(a.price)??Infinity)-(priceAmount(b.price)??Infinity);
    });
  },[allFindings,run?.trip_details?.budget_usd]);
  const selectedOption=rankedOptions[selectedOptionIndex];
  const bookingSource=selectedOption?.booking_source_id?sources.find(source=>source.source_id===selectedOption.booking_source_id):null;
  const acceptedBookingSource=acceptedOption?.booking_source_id?sources.find(source=>source.source_id===acceptedOption.booking_source_id):null;
  const selectedSources=(selectedOption?.source_ids||[]).map(id=>sources.find(source=>source.source_id===id)).filter(Boolean);
  const decisionPanel=run?.status==='research_complete'&&<section className="decision-section" id="decision" aria-live="polite"><div className="section-header"><div><span className="section-kicker">YOUR NEXT STEP</span><h2>{run.limited_mode?'Review live search results':'Choose a recovery option'}</h2><p>{run.limited_mode?'These are cited search leads; verify service details and availability.':'Options are ordered by budget fit and available source evidence.'}</p></div>{rankedOptions.length>0&&<div className="round-count">Option {Math.min(selectedOptionIndex+1,rankedOptions.length)} of {rankedOptions.length}</div>}</div>
    {!rankedOptions.length?<div className="research-empty compact"><CircleAlert size={20}/><b>No source-backed option found</b><p>The agents couldn’t verify a specific flight, bus, or train from their web results. Check the sources or search again.</p></div>:acceptedOption?<div className="accepted-option"><div className="plane-flight" aria-hidden="true"><Plane size={34}/><span/></div><div><span className="section-kicker">OPTION SELECTED</span><h3>{acceptedOption.title}</h3><p>{acceptedOption.summary}</p>{acceptedBookingSource?<a className="primary ticket-link" href={acceptedBookingSource.url} target="_blank" rel="noreferrer">Open exact itinerary <ArrowUpRight size={18}/></a>:<p className="no-booking-link">No direct purchase page was verified. Use the cited source to check this service with the operator.</p>}<SourceLinks sourceIds={acceptedOption.source_ids} sources={sources}/></div></div>:noOptionsLeft?<div className="research-empty compact"><X size={20}/><b>You’ve reviewed all {rankedOptions.length} options</b><p>Revisit an option above or search again with different trip details.</p><button className="decision-secondary" onClick={()=>{setSelectedOptionIndex(0);setNoOptionsLeft(false)}}>Show the top option</button></div>:<article className="best-option-card"><div className="best-option-label"><Sparkles size={17}/>{run.limited_mode?'LIVE WEB RESULT · VERIFY DETAILS':'BEST AVAILABLE OPTION'}</div><div className="finding-top"><span>{selectedOption.transport_mode||'Travel option'}</span><small>{run.limited_mode?`Source result · ${selectedOption.agent_name}`:`Recommended by ${selectedOption.agent_name}`}</small></div><h3>{selectedOption.title}</h3><p>{selectedOption.summary}</p><div className="finding-meta">{selectedOption.price&&<span><Wallet size={14}/>{selectedOption.price}</span>}{selectedOption.departure&&<span><Clock3 size={14}/>Leaves {selectedOption.departure}</span>}{selectedOption.arrival&&<span><MapPin size={14}/>Arrives {selectedOption.arrival}</span>}</div>{bookingSource?<a className="direct-booking-link" href={bookingSource.url} target="_blank" rel="noreferrer"><Link2 size={14}/>{bookingSource.title}<ArrowUpRight size={13}/></a>:<div className="source-links">{selectedSources.map(source=><a href={source.url} target="_blank" rel="noreferrer" key={source.source_id}><Link2 size={13}/>{source.title}<ArrowUpRight size={12}/></a>)}</div>}{run.limited_mode&&<div className="source-links"><a href={googleFlightsSearchUrl(run.trip_details)} target="_blank" rel="noreferrer">Search this route on Google Flights <ArrowUpRight size={12}/></a><a href={googleSearchUrl(run.trip_details)} target="_blank" rel="noreferrer">Search the route on Google <ArrowUpRight size={12}/></a></div>}<div className="decision-buttons"><button className="primary" onClick={()=>setAcceptedOption(selectedOption)}><Check size={18}/>{run.limited_mode?'Open selected source':'Yes, this works'}</button><button className="decision-secondary" onClick={()=>{if(selectedOptionIndex+1>=rankedOptions.length)setNoOptionsLeft(true);else setSelectedOptionIndex(index=>index+1)}}><X size={18}/>{selectedOptionIndex+1>=rankedOptions.length?'No, finish reviewing':'No, show next option'}</button></div></article>}
  </section>;

  return <main className="app-shell">
    <header className="topbar"><a href="#top" className="brand" aria-label="KOI home">KOI<span className="brand-mark">●</span></a><div className="status-pill"><span className={`status-dot ${connection}`}/>{connection==='connected'?'Connected':connection==='connecting'?'Connecting':connection==='complete'?'Research complete':'Ready'}</div></header>

    <section className="hero" id="top"><div className="eyebrow"><Sparkles size={16}/> TRAVEL DISRUPTION ASSISTANT</div><h1>KOI</h1><p className="tagline">Your flight changed. Find your next way forward.</p><p className="hero-copy">Share your flight details. KOI checks live travel options and compares alternatives.</p></section>

    <nav className="page-nav" aria-label="Page sections"><button onClick={()=>jumpTo('trip')}>Trip details</button>{run?.status==='research_complete'&&<button onClick={()=>jumpTo('decision')}>Best match</button>}<button onClick={()=>jumpTo('research')}>How it works</button>{run&&<button onClick={()=>jumpTo('sources')}>More options</button>}</nav>

    {message&&<div className={`notice ${message.startsWith('Could not')?'error':'info'}`} role="status">{message.startsWith('Could not')&&<CircleAlert size={17}/>}<span>{message}</span></div>}
    {run?.error&&<div className="notice error"><CircleAlert size={17}/><span>{run.error}</span></div>}

    <section className="trip-layout" id="trip">
      <div className="trip-intro"><span className="section-kicker">START HERE</span><h2>Find another way there.</h2><p>Enter your cancelled flight. KOI looks for live alternatives.</p><p className="required-hint">Required: flight number, airline, route, and date.</p><details className="privacy-note"><summary>How KOI uses your details</summary><p>Your flight number, airline, route, date, and preferences go to Ollama Cloud for live web searches and agent analysis. Do not enter a booking reference or passenger personal information.</p></details></div>
      <form className="trip-form" onSubmit={startResearch}>
        <div className="form-heading"><div><span className="section-kicker">CANCELLED FLIGHT</span><h3>Flight details</h3></div><Plane size={22}/></div>
        <div className="form-grid">
          <label>Flight number<input name="flight_number" value={form.flight_number} onChange={updateField} placeholder="e.g. UA 123" required maxLength="16" disabled={busy}/></label>
          <label>Airline<input name="airline" value={form.airline} onChange={updateField} placeholder="e.g. United Airlines" required maxLength="80" disabled={busy}/></label>
          <label>Leaving from<input name="origin" value={form.origin} onChange={updateField} placeholder="City or airport" required disabled={busy}/></label>
          <label>Going to<input name="destination" value={form.destination} onChange={updateField} placeholder="City or airport" required disabled={busy}/></label>
          <label>Travel date<input type="date" name="travel_date" value={form.travel_date} onChange={updateField} required disabled={busy}/></label>
        </div>
        <details className="advanced-preferences"><summary><span><b>More preferences</b><small>Budget, arrival time, or plans (optional)</small></span><ChevronDown size={18}/></summary><div className="form-grid advanced-grid">
          <label>Maximum budget (USD)<span className="optional-label">Default: $300</span><input type="number" name="budget_usd" min="1" max="100000" value={form.budget_usd} onChange={updateField} required disabled={busy}/></label>
          <label className="full-field">Need to arrive by <span className="optional-label">Optional</span><input name="arrive_by" value={form.arrive_by} onChange={updateField} placeholder="e.g. 4:30 PM" maxLength="120" disabled={busy}/></label>
          <label className="full-field">Important plans to protect <span className="optional-label">Optional · one per line</span><textarea name="important_plans" value={form.important_plans} onChange={updateField} placeholder={'e.g. 5 PM presentation\nDinner at 7:30 PM'} rows="3" disabled={busy}/></label>
        </div></details>
        <button className="primary submit-button" type="submit" disabled={busy||!config||config.offline||!config.ollama_key_configured||!config.model_configured}><Search size={19}/>{busy?'Agents are searching…':'Search live options'}<ArrowRight size={18}/></button>
        <div className="form-footnote">{config?.offline?'KOI is offline. Start the backend to continue.':config?.ollama_key_configured&&config?.model_configured?'Ready to search for alternatives.':'KOI needs setup before you can search.'}</div>
      </form>
    </section>

    {decisionPanel}

    <section className="research-section" id="research">
      {busy&&<div className="thinking-panel" role="status" aria-live="polite"><div className="thinking-orbit"><span/><span/><span/><Search size={23}/></div><div><b>{responses.length?'Checking the best options':'Searching live travel options'}</b><div className="thinking-progress"><i/></div></div><span className="thinking-label">LIVE</span></div>}
      <details className="research-disclosure"><summary><span><b>How KOI found this recommendation</b><small>{run?`${responses.length} updates from 4 agents`:'See how the travel search works'}</small></span><ChevronDown size={19}/></summary><div className="research-content">
      <div className="section-header"><div><span className="section-kicker">LIVE INVESTIGATION</span><h2>Agent research</h2><p>Four agents cross-check travel options.</p></div><div className="round-count"><Users size={17}/>{run?`${responses.length} updates`:'4 agents'}</div></div>

      <details className="agent-team"><summary><span className="team-summary-icon"><Users size={18}/></span><span><b>Meet the agent team</b><small>Open to see what each agent searches for</small></span><ChevronDown size={18}/></summary><div className="team-grid">{Object.entries(agentInfo).map(([name,info])=>{const Icon=info.icon;const active=run?.active_agents?.includes(name);return <article className={`team-member ${active?'is-active':''}`} key={name}><span className={`agent-icon ${info.color}`}><Icon size={19}/></span><div><b>{name}</b><small>{info.role}</small><em>{agentProgress[name]|| (active?'Ready to search':'Waiting')}</em></div></article>})}</div></details>

      {!run&&<div className="research-empty"><Search size={22}/><b>Your research will appear here</b><p>Submit flight details to start live web searches and agent discussions.</p></div>}
      {run&&rounds.map(([round,items])=><details className="round-block round-details" key={round}><summary><span>Round {round+1}</span>{round===0?'Initial research':'Peer review'} · {items.length} short updates<ChevronDown size={17}/></summary><div className="response-grid">{items.map(response=><ResponseCard key={response.message_id} response={response} sources={sources}/>)}</div></details>)}
      {run?.status==='research_complete'&&<div className="completion-note"><Check size={18}/><span><b>Research complete.</b> Confirm the current fare and schedule before booking.</span></div>}
      </div></details>
    </section>

    <details className="findings-section sources-disclosure" id="sources">
      <summary><span><b>More options and web sources</b><small>{sources.length?`${allFindings.length} options · ${sources.length} sources`:'See other travel options and where they came from'}</small></span><ChevronDown size={19}/></summary><div className="sources-content">
      <div className="section-header"><div><span className="section-kicker">WEB EVIDENCE</span><h2>Other options</h2><p>Open an option to see its details and sources.</p></div><div className="round-count"><Link2 size={17}/>{sources.length} sources</div></div>
      {!sources.length?<div className="research-empty compact"><Link2 size={20}/><b>Sources appear when a live search starts</b></div>:<>
        {visibleFindings.length>0&&<div className="findings-grid">{visibleFindings.map((finding,index)=><article className="finding-card" key={`${finding.agent_name}-${index}`}><div className="finding-top"><span>{finding.transport_mode||'Travel option'}</span><small>{finding.agent_name}</small></div><h3>{finding.title}</h3><div className="finding-meta">{finding.price&&<span><Wallet size={14}/>{finding.price}</span>}{finding.departure&&<span><Clock3 size={14}/>Leaves {finding.departure}</span>}{finding.arrival&&<span><MapPin size={14}/>Arrives {finding.arrival}</span>}</div><details className="finding-details"><summary>Details and sources</summary><p>{finding.summary}</p><SourceLinks sourceIds={finding.source_ids} sources={sources}/></details></article>)}</div>}
        {additionalFindings.length>0&&<details className="more-findings"><summary>Show {additionalFindings.length} more options</summary><div className="findings-grid">{additionalFindings.map((finding,index)=><article className="finding-card" key={`${finding.agent_name}-extra-${index}`}><div className="finding-top"><span>{finding.transport_mode||'Travel option'}</span><small>{finding.agent_name}</small></div><h3>{finding.title}</h3><div className="finding-meta">{finding.price&&<span><Wallet size={14}/>{finding.price}</span>}{finding.departure&&<span><Clock3 size={14}/>Leaves {finding.departure}</span>}{finding.arrival&&<span><MapPin size={14}/>Arrives {finding.arrival}</span>}</div><details className="finding-details"><summary>Details and sources</summary><p>{finding.summary}</p><SourceLinks sourceIds={finding.source_ids} sources={sources}/></details></article>)}</div></details>}
        <details className="all-sources"><summary>View all {sources.length} web sources</summary><div className="source-list">{sources.map(source=><article className="source-card" key={source.source_id}><span className="source-number">{source.source_id.replace('web-','')}</span><div><a href={source.url} target="_blank" rel="noreferrer">{source.title}<ArrowUpRight size={14}/></a><p>{source.snippet||'No preview available. Open the source to review its details.'}</p>{source.page_excerpt&&<details className="page-excerpt"><summary>Read fetched page excerpt</summary><p>{source.page_excerpt}</p></details>}<small>Found by {(source.found_by||[]).join(', ')} · retrieved {new Date(source.retrieved_at).toLocaleTimeString()}</small></div></article>)}</div></details>
      </>}
      </div>
    </details>

    <footer><span className="footer-brand">KOI</span><span>Live web search · Confirm fare and availability with the operator</span><span>KOI · Cisco Cloud AI</span></footer>
  </main>
}

function ResponseCard({response,sources}){
  const cited=(response.supporting_facts||[]).map(id=>sources.find(source=>source.source_id===id)).filter(Boolean);
  const brief=response.findings?.[0]?.summary||response.reason;
  const statusLabel=response.call_status==='success'?'Reviewed':response.call_status==='fallback'?'Web results only':response.call_status.replaceAll('_',' ');
  return <article className={`response-card agent-${response.agent_name.toLowerCase()}`}><div className="response-head"><span className="response-agent">{response.agent_name}</span><span className={`call-status ${response.call_status}`}>{statusLabel}</span></div><p className="agent-brief">{brief}</p><small className="agent-count">{response.findings?.length?response.call_status==='fallback'?`${response.findings.length} live source result${response.findings.length===1?'':'s'}`:`${response.findings.length} option${response.findings.length===1?'':'s'} reviewed`:'No verified option'}</small>
    <details className="agent-details"><summary>Agent details</summary><div className="agent-details-body"><p>{response.reason}</p>
      {response.findings?.length>0&&<div className="agent-findings">{response.findings.map((finding,index)=><div className="agent-finding" key={index}><b>{finding.title}</b><span>{finding.summary}</span><small>{finding.transport_mode}{finding.price?` · ${finding.price}`:''}{finding.arrival?` · arrives ${finding.arrival}`:''}</small><SourceLinks sourceIds={finding.source_ids} sources={sources}/></div>)}</div>}
      {response.objections?.map((objection,index)=><div className="objection" key={index}><b>{objection.agent_name?`Question for ${objection.agent_name}`:'Concern'}</b><span>{objection.concern}</span><small>{objection.question}</small></div>)}
      {response.proposal_changed&&<div className="changed">Revised after peer review · {response.change_reason}</div>}
      {response.missing_information?.length>0&&<div className="missing-info"><b>Still to confirm</b><ul>{response.missing_information.map((item,index)=><li key={index}>{item}</li>)}</ul></div>}
      {response.error&&<div className="response-error">{response.error}</div>}
      <details className="response-sources"><summary><Link2 size={14}/>{cited.length?`${cited.length} cited sources`:'Search trace'}<ChevronDown size={15}/></summary><div className="trace"><p><b>Search query:</b> {response.tool_calls?.[0]?.arguments?.query}</p>{cited.map(source=><p key={source.source_id}><a href={source.url} target="_blank" rel="noreferrer">{source.title} <ArrowUpRight size={12}/></a></p>)}</div></details>
    </div></details>
  </article>
}

function SourceLinks({sourceIds=[],sources=[]}){const found=sourceIds.map(id=>sources.find(source=>source.source_id===id)).filter(Boolean);if(!found.length)return null;return <div className="source-links">{found.map(source=><a href={source.url} target="_blank" rel="noreferrer" key={source.source_id}><Link2 size={13}/>{source.source_id}<ArrowUpRight size={12}/></a>)}</div>}
