
import { CheckCircle2, CircleDashed, Route } from "lucide-react";

function RecoveryPlan({ disrupted = false }) {
  return (
    <section
      id="recovery"
      className="rounded-2xl border border-[#D6EAF7] bg-white p-5 shadow-sm"
    >
      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-bold text-[#36546B]">
          Your recovery plan
        </h2>

        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            disrupted
              ? "bg-[#FFF0EC] text-[#D9695D]"
              : "bg-[#E8F7F1] text-[#458C75]"
          }`}
        >
          {disrupted ? "Pending" : "On track"}
        </span>
      </div>

      {/* Before disruption */}
      {!disrupted && (
        <div className="flex flex-col items-center rounded-xl border border-[#E2EEF7] bg-[#FAFDFF] px-5 py-10 text-center">
          <div className="mb-4 rounded-full bg-[#EAF5FD] p-4">
            <CheckCircle2
              size={28}
              className="text-[#65A88C]"
            />
          </div>

          <h3 className="text-lg font-semibold text-[#36546B]">
            Everything looks good!
          </h3>

          <p className="mt-2 text-sm leading-relaxed text-[#7A9AB0]">
            Your plans are on track. If anything changes,
            Koi will help you find a way forward.
          </p>
        </div>
      )}

      {/* After disruption */}
      {disrupted && (
        <div className="rounded-xl border border-[#E2EEF7] bg-[#FAFDFF] p-6">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-full bg-[#EAF5FD] p-3">
              <Route size={24} className="text-[#5684A3]" />
            </div>

            <div>
              <h3 className="font-semibold text-[#36546B]">
                Recovery needed
              </h3>

              <p className="text-xs text-[#7A9AB0]">
                Flight cancellation detected
              </p>
            </div>
          </div>

          <div className="rounded-lg bg-white p-4">
            <div className="flex items-center gap-2">
              <CircleDashed
                size={18}
                className="text-[#ED897B]"
              />

              <p className="text-sm font-medium text-[#36546B]">
                Awaiting agent recommendations
              </p>
            </div>

            <p className="mt-2 text-xs leading-relaxed text-[#7A9AB0]">
              Travel, Budget, and Commitments agents will
              work together to find a suitable recovery plan.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

export default RecoveryPlan;
