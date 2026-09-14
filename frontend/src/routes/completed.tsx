import { createFileRoute } from "@tanstack/react-router";
import { JobsPage } from "../components/JobsPage";

export const Route = createFileRoute("/completed")({ component: Completed });

function Completed() {
  return (
    <JobsPage
      tab="completed"
      heading="Completed videos"
      filterJob={(job) => job.status === "completed"}
      emptyTitle="Nothing here yet"
      emptyBody="Videos will appear here as they move through the pipeline."
    />
  );
}
