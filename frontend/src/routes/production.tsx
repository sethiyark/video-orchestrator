import { createFileRoute } from "@tanstack/react-router";
import { JobsPage } from "../components/JobsPage";

export const Route = createFileRoute("/production")({ component: Production });

function Production() {
  return (
    <JobsPage
      tab="production"
      heading="Video pipeline"
      filterJob={(job, showCompleted) =>
        showCompleted || job.status !== "completed"
      }
      emptyTitle="Your next story starts here"
      emptyBody="Add a video idea and watch it move from research to review."
      showCompletedToggle
      showNewVideoButton
    />
  );
}
