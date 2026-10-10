
import { Plane, Hotel, BriefcaseBusiness } from "lucide-react";

const itinerary = [
  {
    id: 1,
    title: "SFO → NYC",
    description: "UA 1234 · 9:00 AM – 5:15 PM",
    status: "Scheduled",
    icon: Plane,
    impact: "Your original flight is no longer available.",
  },
  {
    id: 2,
    title: "Hotel",
    description: "The James New York · Apr 15–17",
    status: "Upcoming",
    icon: Hotel,
    impact: "Your arrival time may affect hotel check-in.",
  },
  {
    id: 3,
    title: "Presentation",
    description: "Client Meeting · 5:00 PM",
    status: "Important",
    icon: BriefcaseBusiness,
    impact: "Your presentation may be missed due to the delay.",
  },
];

function MyTrip({ disrupted = false }) {
  return (
    <section
      id="trip"
      className="rounded-2xl border border-[#D6EAF7] bg-white p-5 shadow-sm"
    >
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-bold text-[#36546B]">
          Your trip
        </h2>
        <span className="text-sm text-[#7A9AB0]">Apr 15</span>
      </div>

      <div className="space-y-3">
        {itinerary.map((item) => {
          const Icon = item.icon;
          const isCanceled = disrupted && item.id === 1;
          const isAtRisk = disrupted && item.id !== 1;

          const status = isCanceled
            ? "Canceled"
            : isAtRisk
            ? "At risk"
            : item.status;

          const cardStyle = isCanceled
            ? "border-[#F8D9D5] bg-[#FFF5F3]"
            : isAtRisk
            ? "border-[#F5E4C5] bg-[#FFFBF2]"
            : "border-[#E2EEF7] bg-[#FAFDFF]";

          const badgeStyle = isCanceled
            ? "bg-[#FFE2DD] text-[#D9695D]"
            : isAtRisk
            ? "bg-[#FFF0D5] text-[#B77A30]"
            : "bg-[#EAF5FD] text-[#5684A3]";

          return (
            <div
              key={item.id}
              className={`rounded-xl border p-4 transition-colors duration-300 ${cardStyle}`}
            >
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#EAF5FD]">
                  <Icon
                    size={22}
                    className={
                      isCanceled
                        ? "text-[#ED897B]"
                        : "text-[#5684A3]"
                    }
                  />
                </div>

                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[#36546B]">
                    {item.title}
                  </h3>
                  <p className="mt-1 text-xs text-[#7A9AB0]">
                    {item.description}
                  </p>
                </div>

                <span
                  className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-medium ${badgeStyle}`}
                >
                  {status}
                </span>
              </div>

              {disrupted && (
                <p
                  className={`mt-3 border-t pt-3 text-xs ${
                    isCanceled
                      ? "border-[#F8D9D5] text-[#D9695D]"
                      : "border-[#F5E4C5] text-[#B77A30]"
                  }`}
                >
                  {item.impact}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {disrupted && (
        <div className="mt-4 rounded-xl bg-[#EAF5FD] p-3 text-center">
          <p className="text-xs font-medium text-[#36546B]">
            1 cancellation · 2 commitments potentially affected
          </p>
        </div>
      )}
    </section>
  );
}

export default MyTrip;
