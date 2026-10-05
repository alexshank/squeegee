import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { RawValue, csvRows, infer, unquote } from "./RawValue";

test("a record is pretty printed JSON", () => {
  expect(infer({ id: 1 }, null)).toEqual({ text: '{\n  "id": 1\n}', language: "json" });
});

test("a string holding JSON is JSON, whatever the stage says", () => {
  expect(infer('{"id":1}', "csv").language).toBe("json");
});

test("a string is CSV only when the stage says so, and plain text otherwise", () => {
  expect(infer("1,$29.99", "csv")).toEqual({ text: "1,$29.99", language: "csv" });
  expect(infer("hello, world", null)).toEqual({ text: "hello, world", language: null });
});

test("a quoted comma stays inside its CSV field", () => {
  expect(csvRows('1,"Smith, Jo","say ""hi"""')).toEqual([["1", '"Smith, Jo"', '"say ""hi"""']]);
  expect(csvRows("a,,b\r\n")).toEqual([["a", "", "b"]]);
});

test("a line break inside a quoted field stays in its field", () => {
  expect(csvRows('id,items\n1009,"sticker x1;\ngift wrap x1"')).toEqual([
    ["id", "items"],
    ["1009", '"sticker x1;\ngift wrap x1"'],
  ]);
});

test("text with a header and rows that agree on their columns is CSV", () => {
  expect(infer("id,amount\n1,$29.99", null).language).toBe("csv");
  expect(infer("hello, world\nnot, a, table", null).language).toBe(null);
});

test("a quoted CSV field reads as its value in the table", () => {
  expect(unquote('"say ""hi"""')).toBe('say "hi"');
  expect(unquote("plain")).toBe("plain");
});

test("CSV can be switched to a table with its header as column names", () => {
  render(<RawValue label="input" value={'id,note,items\n1,"a, b","x;\ny"'} format="csv" />);

  fireEvent.click(screen.getByText("view as table"));

  expect(screen.getByRole("columnheader", { name: "note" })).toBeDefined();
  expect(screen.getByRole("cell", { name: "a, b" })).toBeDefined();
  // the quoted line break stays inside its cell instead of starting a row
  expect(screen.getAllByRole("row")).toHaveLength(2);
  expect(screen.getByText("view as text")).toBeDefined();
});
