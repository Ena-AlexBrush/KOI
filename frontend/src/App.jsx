
import { UserRound, Fish } from "lucide-react";
import { useState } from "react";
import MyTrip from "./components/MyTrip";
import RecoveryPlan from "./components/RecoveryPlan";
import AgentConversation from "./components/AgentConversation";

function App() {
  const [disrupted, setDisrupted] = useState(false);
  return (
    <div className="min-h-screen bg-[#EAF5FD] text-[#36546B]">

      {/* Navigation */}
      <header className="border-b border-[#D6EAF7] bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-8 py-5">

          {/* Logo */}
          <div className="flex items-center gap-2">
            <Fish size={32} className="text-[#ED897B]" />
            <span className="font-display text-3xl tracking-tight text-[#ED897B]">
              koi
            </span>
          </div>

          {/* Navigation links */}
          <nav className="flex items-center gap-10">
            <a href="#trip" className="font-medium hover:text-[#ED897B]">
              My Trip
            </a>
            <a href="#recovery" className="font-medium hover:text-[#ED897B]">
              Recovery
            </a>
            <a href="#agents" className="font-medium hover:text-[#ED897B]">
              Agent Conversation
            </a>
          </nav>

          {/* Profile */}
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#D6EAF7]">
            <UserRound size={21} className="text-[#36546B]" />
          </div>

        </div>
      </header>

      
{/* Main Content */}
<main className="mx-auto max-w-7xl px-6 py-8">

  {/* Sky Hero Banner */}
  <section
    className="relative overflow-hidden rounded-3xl border border-[#D6EAF7] px-10 py-8 shadow-sm"
    style={{
      background:
        "linear-gradient(115deg, #FFFFFF 0%, #EAF5FD 45%, #C7E8FA 100%)",
    }}
  >
    {/* Decorative sky elements */}
    <div className="pointer-events-none absolute right-16 top-8 h-24 w-40 rounded-full bg-white/50 blur-3xl" />
    <div className="pointer-events-none absolute right-48 bottom-0 h-20 w-56 rounded-full bg-white/70 blur-2xl" />

    <div className="relative z-10 max-w-2xl">
      <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-[#5684A3]">
        Your plans, protected.
      </p>

      <h1 className="font-display text-4xl leading-tight tracking-tight text-[#ED897B] md:text-5xl">
        One change.
        <br />
        Everything handled.
      </h1>

      <p className="mt-4 text-lg text-[#36546B]">
        A calmer way to recover when your travel plans change.
      </p>

      <a
        href="#trip"
        className="mt-7 inline-flex items-center rounded-xl bg-[#ED897B] px-6 py-3 font-semibold text-white shadow-sm transition hover:bg-[#DF7468]"
      >
        Explore your trip →
      </a>
      <button
        onClick={() => setDisrupted(!disrupted)}
        className="ml-3 mt-3 rounded-xl border border-[#ED897B] px-5 py-3 font-semibold text-[#ED897B] transition hover:bg-[#FFF1EE]"
      >
        {disrupted ? "Reset Trip" : "Simulate Cancellation"}
      </button>

    </div>
  </section>



{/* Dashboard */}
<div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
  <MyTrip disrupted={disrupted} />

  <AgentConversation disrupted={disrupted} />

  <RecoveryPlan disrupted={disrupted} />
</div>
  

</main>


    </div>
  );
}

export default App;
