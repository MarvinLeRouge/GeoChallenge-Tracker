import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";

describe("LoadingIndicator", () => {
  it("renders the given label", () => {
    const wrapper = mount(LoadingIndicator, {
      props: { label: "Chargement des targets…" },
    });

    expect(wrapper.text()).toContain("Chargement des targets…");
  });

  it("renders a spinning icon", () => {
    const wrapper = mount(LoadingIndicator, {
      props: { label: "Chargement…" },
    });

    expect(wrapper.find("svg.animate-spin").exists()).toBe(true);
  });
});
