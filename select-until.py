import sublime, sublime_plugin
from sublime import Region

import re

# In ST3, view.find returns Region(-1,-1) if there are no occurrences.
# In ST2, however, it returns None, so we have to check for that.
def safe_end(region):
	if region is None:
		return -1
	return region.end()

def clean_up(view):
	view.erase_regions("select-until-extended")
	view.erase_regions("select-until")
	view.erase_regions("select-until-originals")
	SelectUntilCommand.running = False

def on_done(view, extend):
	if extend:
		newSels = view.get_regions("select-until-extended")
	else:
		newSels = view.get_regions("select-until")

	sels = view.sel()
	sels.clear()
	for sel in newSels:
		sels.add(sel)

	SelectUntilCommand.prevSelector = SelectUntilCommand.temp or SelectUntilCommand.prevSelector
	clean_up(view)

rSelector = re.compile("^(-?)(?:\{(-?\d+)\}|\[(.+)\]|/(.+)/|(.*))$")
def find_matching_point(view, sel, selector):
	if selector == "": return -1

	result = rSelector.search(selector)

	groups = result.groups()
	isReverse = (groups[0] == "-")
	num = int(groups[1]) if groups[1] is not None else None
	chars = groups[2] or groups[4]
	regex = groups[3]
	searchForward = isReverse ^ SelectUntilCommand.searchForward

	if searchForward:
		if num is not None: return sel.end() + num
		elif regex is not None: return safe_end(view.find(regex, sel.end()))
		else: return safe_end(view.find(chars, sel.end(), sublime.LITERAL))

	else:
		if num is not None: return sel.begin() - num
		elif regex is not None: regions = view.find_all(regex)
		else: regions = view.find_all(chars, sublime.LITERAL)

		for region in reversed(regions):
			if region.end() <= sel.begin():
				return region.begin()

	return -1

def on_change(view, oriSels, selector, extend):
	SelectUntilCommand.temp = selector
	extendedSels = []
	newSels = []
	for sel in oriSels:
		point = find_matching_point(view, sel, selector)

		if point is -1: point = sel.b #try to keep this selection the same

		region = Region(point, point)

		extendedSel = sel.cover(region)
		extendedSels.append(extendedSel)

		newSels.append(region)

	view.add_regions("select-until-originals", oriSels, "comment", "", sublime.DRAW_EMPTY)
	if extend:
		view.erase_regions("select-until")
		view.add_regions("select-until-extended", extendedSels, "entity", "", sublime.DRAW_OUTLINED)
	else:
		view.erase_regions("select-until-extended")
		view.add_regions("select-until", newSels, "entity", "", sublime.DRAW_EMPTY)

def on_cancel(view, oriSels):
	sels = view.sel()
	sels.clear()
	for sel in oriSels:
		sels.add(sel)

	clean_up(view)

class SelectUntilCommand(sublime_plugin.TextCommand):
	temp = ""
	prevSelector = ""

	#If we get called again while the quick panel's up, on_cancel gets called.
	#There's no way in the API to distinguish this from the user pressing esc, so
	#we have to do it ourselves.
	running = False
	searchForward = True

	def run(self, edit, extend):
		#Make sure the view never refers to the quick panel - if we hit the shortcut
		#while the panel is up, the wrong view is targetted.
		view = self.view.window().active_view_in_group(self.view.window().active_group())

		if SelectUntilCommand.running:
			if SelectUntilCommand.extend == extend:
				SelectUntilCommand.searchForward = not SelectUntilCommand.searchForward
			SelectUntilCommand.prevSelector = SelectUntilCommand.temp
		else:
			SelectUntilCommand.searchForward = True
		SelectUntilCommand.running = True
		SelectUntilCommand.extend = extend

		#We have to use set_timeout here; otherwise the quick panel doesn't actually
		#update correctly if we open it a second time. Seems to be a bug in Sublime.
		sublime.set_timeout(lambda : self.show_panel(view, extend), 0)

	def show_panel(self, view, extend):
		oriSels = [ sel for sel in view.sel() ]
		direction = "Next" if SelectUntilCommand.searchForward else "Previous"
		v = view.window().show_input_panel(
			"Select Until {} -- chars or [chars] or {{count}} or /regex/. Use minus (-) or press shortcut again to reverse search:".format(direction),
			SelectUntilCommand.prevSelector,
			lambda selector: on_done(view, extend),
			lambda selector: on_change(view, oriSels, selector, extend),
			lambda : on_cancel(view, oriSels)
		)
		v.sel().clear()
		v.sel().add(sublime.Region(0, len(SelectUntilCommand.prevSelector)))

class ReverseSelectCommand(sublime_plugin.TextCommand):

	def run(self, edit):
		sels = self.view.sel()

		newSels = []
		for sel in sels:
			newSels.append(Region(sel.b, sel.a))

		sels.clear()
		for sel in newSels:
			sels.add(sel)
