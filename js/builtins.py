from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .runtime import JSObject, NativeFunction


@dataclass
class DocumentBridge:
	get_title: Callable[[], str]
	set_title: Callable[[str], None]
	get_element_text: Callable[[str], str] | None = None
	set_element_text: Callable[[str, str], None] | None = None

	def __post_init__(self):
		self._elements: dict[str, ElementBridge] = {}

	@property
	def title(self) -> str:
		return self.get_title()

	@title.setter
	def title(self, value: Any):
		self.set_title(str(value))

	def getElementById(self, element_id: Any):
		eid = str(element_id)
		element = self._elements.get(eid)
		if element is None:
			element = ElementBridge(
				element_id=eid,
				get_text=(lambda: self.get_element_text(eid) if self.get_element_text else ""),
				set_text=(lambda value: self.set_element_text(eid, value) if self.set_element_text else None),
			)
			self._elements[eid] = element
		return element


@dataclass
class ElementBridge:
	element_id: str
	get_text: Callable[[], str]
	set_text: Callable[[str], None]

	@property
	def textContent(self) -> str:
		return self.get_text()

	@textContent.setter
	def textContent(self, value: Any):
		self.set_text(str(value))

	def addEventListener(self, _event_name: Any, _listener: Any):
		# Static rendering has no event loop yet, so listener registration is a no-op.
		return None


@dataclass
class LocationBridge:
	get_href: Callable[[], str]
	set_href: Callable[[str], None]
	navigate: Callable[[str], None] | None = None

	@property
	def href(self) -> str:
		return self.get_href()

	@href.setter
	def href(self, value: Any):
		text = str(value)
		self.set_href(text)
		if self.navigate:
			self.navigate(text)

	def replace(self, value: Any):
		text = str(value)
		self.set_href(text)
		if self.navigate:
			self.navigate(text)


def _to_console_text(value: Any) -> str:
	if value is None:
		return "null"
	if isinstance(value, bool):
		return "true" if value else "false"
	return str(value)


def default_globals(
	*,
	document: DocumentBridge | None = None,
	location: LocationBridge | None = None,
	console_logger: Callable[[str], None] | None = None,
) -> dict[str, Any]:
	log_fn = console_logger or (lambda msg: None)

	def console_log(*args):
		log_fn(" ".join(_to_console_text(x) for x in args))
		return None

	console = JSObject(
		{
			"log": NativeFunction(console_log, name="console.log"),
		}
	)

	math = JSObject(
		{
			"abs": NativeFunction(lambda x: abs(float(x)), name="Math.abs"),
			"min": NativeFunction(lambda *xs: min(float(x) for x in xs), name="Math.min"),
			"max": NativeFunction(lambda *xs: max(float(x) for x in xs), name="Math.max"),
			"round": NativeFunction(lambda x: round(float(x)), name="Math.round"),
			"floor": NativeFunction(lambda x: int(float(x) // 1), name="Math.floor"),
			"ceil": NativeFunction(
				lambda x: int(float(x)) if float(x).is_integer() else int(float(x)) + 1,
				name="Math.ceil",
			),
		}
	)

	window = JSObject(
		{
			"console": console,
			"Math": math,
		}
	)

	globals_dict: dict[str, Any] = {
		"console": console,
		"Math": math,
		"window": window,
	}

	if document is not None:
		globals_dict["document"] = document
		window.set("document", document)

	if location is not None:
		globals_dict["location"] = location
		window.set("location", location)
		window.set(
			"alert",
			NativeFunction(lambda msg=None: log_fn(f"alert: {_to_console_text(msg)}"), name="alert"),
		)

	return globals_dict
