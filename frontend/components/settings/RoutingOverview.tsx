import { RecordSection } from "@/components/records/RecordSection";
import { RECORD_CELL, RECORD_HEAD_CELL, RECORD_HEAD_ROW, RECORD_NUMBER_CELL, RECORD_ROW, RECORD_TABLE } from "@/components/records/recordTable";
import { StatusBadge } from "@/components/StatusBadge";
import type { TaskRoute } from "@/lib/routing";

export function RoutingOverview({ tasks }: { tasks: TaskRoute[] }) {
  if (tasks.length === 0) return null;
  return (
    <RecordSection title="Every task" description="The chain each task answers with now, first choice first." testId="routing-overview">
      <div className="overflow-x-auto">
        <table className={`${RECORD_TABLE} min-w-2xl`}>
          <caption className="sr-only">The models each task answers with</caption>
          <thead>
            <tr className={RECORD_HEAD_ROW}>
              <th scope="col" className={RECORD_HEAD_CELL}>
                Task
              </th>
              <th scope="col" className={RECORD_HEAD_CELL}>
                Answering with
              </th>
              <th scope="col" className={`${RECORD_HEAD_CELL} text-end`}>
                In use
              </th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.task} className={RECORD_ROW}>
                <th scope="row" className={`${RECORD_CELL} text-start font-ui text-ui font-medium text-ink-1`}>
                  {task.label}
                </th>
                <td className={`${RECORD_CELL} text-ink-2`}>{task.effectiveChain.length > 0 ? task.effectiveChain.join(" → ") : <StatusBadge tone="error" label="No working model" />}</td>
                <td className={RECORD_NUMBER_CELL}>{`${task.routes.filter((route) => route.enabled).length} of ${task.routes.length}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </RecordSection>
  );
}
