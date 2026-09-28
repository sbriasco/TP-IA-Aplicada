import { act } from "react";

/** Cambia el valor de un input o select de React y dispara el evento que escucha. */
export async function changeValue(
  element: HTMLInputElement | HTMLSelectElement,
  value: string,
): Promise<void> {
  const prototype =
    element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  await act(async () => {
    setter?.call(element, value);
    element.dispatchEvent(
      new Event(element instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }),
    );
  });
}

export async function chooseFile(input: HTMLInputElement, file: File): Promise<void> {
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

export async function click(element: Element): Promise<void> {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

export async function submit(form: HTMLFormElement): Promise<void> {
  await act(async () => {
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
}

export function byLabel<T extends HTMLElement>(container: HTMLElement, text: string): T {
  const label = Array.from(container.querySelectorAll("label")).find(
    (item) => item.textContent === text,
  );
  const element = label?.htmlFor ? container.ownerDocument.getElementById(label.htmlFor) : null;
  if (element === null) {
    throw new Error(`No se encontró el control con etiqueta "${text}".`);
  }
  return element as T;
}

export function byButton(container: HTMLElement, text: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll("button")).find(
    (item) => item.textContent === text,
  );
  if (button === undefined) {
    throw new Error(`No se encontró el botón "${text}".`);
  }
  return button;
}
