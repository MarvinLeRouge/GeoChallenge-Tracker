import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TypeFilterDropdown from "@/components/zones/TypeFilterDropdown.vue";

const options = [
  { code: "traditional", name: "Traditional" },
  { code: "mystery", name: "Mystery" },
];

describe("TypeFilterDropdown", () => {
  it("is closed by default", () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    expect(wrapper.find('[data-testid="dropdown-panel"]').exists()).toBe(false);
  });

  it("opens the panel on toggle button click", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="dropdown-panel"]').exists()).toBe(true);
  });

  it("renders one checkbox per option", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    const checkboxes = wrapper.findAll('input[type="checkbox"]');
    expect(checkboxes).toHaveLength(2);
  });

  it("reflects modelValue as checked state", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: ["mystery"] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    const checkboxes = wrapper.findAll('input[type="checkbox"]');
    expect((checkboxes[0]!.element as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[1]!.element as HTMLInputElement).checked).toBe(true);
  });

  it("emits update:modelValue with the code added when checked", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(true);
    expect(wrapper.emitted("update:modelValue")).toEqual([[["traditional"]]]);
  });

  it("emits update:modelValue with the code removed when unchecked", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: ["traditional", "mystery"] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(false);
    expect(wrapper.emitted("update:modelValue")).toEqual([[["mystery"]]]);
  });
});
