
import { useState } from "react";
import {
  Plane,
  Wallet,
  CalendarDays,
  Route,
  MessageCircle,
} from "lucide-react";

const agents = [
  {
    id: "travel",
    name: "Travel Agent",
    role: "Finds replacement transportation",
    icon: Plane,
    color: "#D6EAF7",
    recommendation: "Searching for replacement flights.",
    activationReason: "Original flight canceled",
  },
  {
    id: "commitments",
    name: "Commitments Agent",
    role: "Protects important plans",
    icon: CalendarDays,
    color: "#E8F7F1",
    recommendation: "Prioritizing your presentation.",
    activationReason: "Arrival change threatens commitments",
  },
  {
    id: "budget",
    name: "Budget Agent",
    role: "Keeps recovery affordable",
    icon: Wallet,
    color: "#FFF0EC",
    recommendation: "Checking options against your $300 budget.",
    activationReason: "Replacement transportation adds costs",
  },
  {
    id: "alternatives",
    name: "Alternatives Agent",
    role: "Explores other transportation methods",
    icon: Route,
    color: "#EAF5FD",
    recommendation: "Looking for alternate transport methods.",
    activationReason: "Original transport options cannot meet constraints",
  },
];

const negotiation = [
  {
    agent: "Travel Agent",
    message: "I recommend the earliest replacement flight.",
  },
  {
    agent: "Budget Agent",
    message: "I disagree. That option may exceed our budget.",
  },
  {
    agent: "Commitments Agent",
    message: "We must protect the presentation deadline.",
  },
];

function AgentConversation({
  disrupted = false,
  activeAgentIds = disrupted
    ? ["travel", "commitments", "budget"]
    : [],
}) {
  const [showNegotiation, setShowNegotiation] = useState(false);

  const activeCount = agents.filter((agent) =>
    activeAgentIds.includes(agent.id)
  ).length;

  return (
    <section
      id="agents"
      className="rounded-2xl border border-[#D6EAF7] bg-white p-5 shadow-sm"
    >
      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-bold text-[#36546B]">
          Agent conversation
        </h2>

        <span className="text-xs text-[#7A9AB0]">
          {activeCount} active · {4 - activeCount} standby
        </span>
      </div>

      {/* Agent cards */}
      <div className="space-y-3">
        {agents.map((agent) => {
          const Icon = agent.icon;
          const isActive = activeAgentIds.includes(agent.id);

          return (
            <div
              key={agent.id}
              className={`rounded-xl border p-3 ${
                isActive
                  ? "border-[#D6EAF7] bg-[#FAFDFF]"
                  : "border-[#EDF1F5] bg-[#FAFBFC]"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                  style={{
                    backgroundColor: agent.color,
                    opacity: isActive ? 1 : 0.65,
                  }}
                >
                  <Icon size={20} className="text-[#36546B]" />
                </div>

                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[#36546B]">
                    {agent.name}
                  </h3>

                  <p className="text-xs text-[#7A9AB0]">
                    {agent.role}
                  </p>
                </div>

                <span
                  className={`rounded-full px-2 py-1 text-[10px] font-medium ${
                    isActive
                      ? "bg-[#E8F7F1] text-[#458C75]"
                      : "bg-[#EDF1F5] text-[#81909E]"
                  }`}
                >
                  {isActive ? "Active" : "Standby"}
                </span>
              </div>

              {disrupted && isActive && (
                <div className="mt-3 rounded-lg bg-[#EAF5FD] p-3">
                  <p className="text-xs text-[#36546B]">
                    {agent.recommendation}
                  </p>

                  <p className="mt-2 text-[11px] text-[#5684A3]">
                    Activated: {agent.activationReason}
                  </p>
                </div>
              )}

              {disrupted && !isActive && (
                <p className="mt-2 text-[11px] text-[#81909E]">
                  Activates when needed
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Negotiation preview */}
      {disrupted ? (
        <div className="mt-5">
          <button
            onClick={() => setShowNegotiation(!showNegotiation)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#ED897B] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#DF7468]"
          >
            <MessageCircle size={17} />
            {showNegotiation
              ? "Hide negotiation"
              : "View negotiation"}
          </button>

          {showNegotiation && (
            <div className="mt-4 space-y-3">
              <p className="text-xs font-semibold text-[#5684A3]">
                Demo preview · Mock agent messages
              </p>

              {negotiation.map((entry, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-[#E2EEF7] bg-[#FAFDFF] p-3"
                >
                  <p className="text-xs font-semibold text-[#5684A3]">
                    {entry.agent}
                  </p>

                  <p className="mt-1 text-sm text-[#36546B]">
                    {entry.message}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="mt-5 text-center text-xs text-[#7A9AB0]">
          Your agents are ready when plans change.
        </p>
      )}
    </section>
  );
}

export default AgentConversation;
