"""
Chooses a set of components to make a running program.
"""

# Copyright (C) 2009, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from zeroinstall import _
import os
from logging import debug, warn, info

from zeroinstall.zerostore import BadDigest, NotStored

from zeroinstall.injector.arch import machine_groups
from zeroinstall.injector import model

class Solver(object):
	"""Chooses a set of implementations to satisfy the requirements of a program and its user.
	Typical use:
	 1. Create a Solver object and configure it
	 2. Call L{solve}.
	 3. If any of the returned feeds_used are stale or missing, you may like to start downloading them
	 4. If it is 'ready' then you can download and run the chosen versions.
	@ivar selections: the chosen implementation of each interface
	@type selections: {L{model.Interface}: Implementation}
	@ivar requires: the selected dependencies for each chosen version
	@type requires: {L{model.Interface}: [L{model.Dependency}]}
	@ivar feeds_used: the feeds which contributed to the choice in L{selections}
	@type feeds_used: set(str)
	@ivar record_details: whether to record information about unselected implementations
	@type record_details: {L{Interface}: [(L{Implementation}, str)]}
	@ivar details: extra information, if record_details mode was used
	@type details: {str: [(Implementation, comment)]}
	"""
	__slots__ = ['selections', 'requires', 'feeds_used', 'details', 'record_details', 'ready']

	def __init__(self):
		self.selections = self.requires = self.feeds_used = self.details = None
		self.record_details = False
		self.ready = False
	
	def solve(self, root_interface, arch, return_postponed=False):
		"""Get the best implementation of root_interface and all of its dependencies.
		@param root_interface: the URI of the program to be solved
		@type root_interface: str
		@param arch: the desired target architecture
		@type arch: L{arch.Architecture}
		@postcondition: self.ready, self.selections and self.feeds_used are updated"""
		raise NotImplementedError("Abstract")

class DefaultSolver(Solver):
	"""The standard (rather naive) Zero Install solver."""
	def __init__(self, network_use, iface_cache, stores, extra_restrictions = None):
		"""
		@param network_use: how much use to make of the network
		@type network_use: L{model.network_levels}
		@param iface_cache: a cache of feeds containing information about available versions
		@type iface_cache: L{iface_cache.IfaceCache}
		@param stores: a cached of implementations (affects choice when offline or when minimising network use)
		@type stores: L{zerostore.Stores}
		@param extra_restrictions: extra restrictions on the chosen implementations
		@type extra_restrictions: {L{model.Interface}: [L{model.Restriction}]}
		"""
		Solver.__init__(self)
		self.network_use = network_use
		self.iface_cache = iface_cache
		self.stores = stores
		self.help_with_testing = False
		self.extra_restrictions = extra_restrictions or {}

	def solve(self, root_interface, arch, return_postponed=False):
		self.selections = {}
		self.requires = {}
		self.feeds_used = set()
		self.details = self.record_details and {}
		self._machine_group = None
		postponed = []

		debug(_("Solve! root = %s"), root_interface)

		def process(dep, arch):
			iface = self.iface_cache.get_interface(dep.interface)
			iface_restrictions = dep.restrictions + self.extra_restrictions.get(iface, [])

			if iface in self.selections:
				impl = self.selections[iface]
				if impl is not None:
					return not get_unusable_reason(impl, iface_restrictions, arch)
				else:
					warn("Interface %s requested twice but first one was failed", iface)
					return True
			self.selections[iface] = None	# Avoid cycles

			impls = get_implementations(iface, arch)
			# sort in reverse mode to use pop()
			impls.sort(lambda a, b: compare(iface, b, a, iface_restrictions, arch))

			if self.record_details:
				self.details[iface] = []
			best = None

			while impls and best is None:
				self.requires[iface] = selected_requires = []
				impl = impls.pop()

				if dep.is_optional() and not get_cached(impl):
					continue

				unusable = get_unusable_reason(impl, iface_restrictions, arch)
				if unusable:
					info(_("Best implementation of %(interface)s is %(best)s, but unusable (%(unusable)s)"), {'interface': iface, 'best': impl, 'unusable': unusable})
					if self.record_details:
						self.details[iface].append((impl, unusable))
					continue

				best = impl
				machine_group_set = False
				if self._machine_group is None and best.machine and best.machine != 'src':
					self._machine_group = machine_groups.get(best.machine, 0)
					debug(_("Now restricted to architecture group %s"), self._machine_group)
					machine_group_set = True
				prev_selections = set(self.selections.keys())
				try:
					for d in impl.requires:
						debug(_("Considering dependency %s"), d)
						use = d.metadata.get("use", None)
						if use not in arch.use:
							info("Skipping dependency; use='%s' not in %s", use, arch.use)
							continue
						if process(d, arch.child_arch):
							selected_requires.append(d)
						elif not d.is_optional():
							best = None
							break
				finally:
					if best is None and impls:
						for i in set(self.selections.keys()) - prev_selections:
							del self.selections[i]
						if machine_group_set:
							self._machine_group = None

				if self.record_details:
					if best is None:
						self.details[iface].append((impl, _("Incompatible with dependency restrictions")))
					else:
						self.details[iface].append((impl, None))

			if self.record_details:
				for impl in impls:
					unusable = get_unusable_reason(impl, iface_restrictions, arch)
					if unusable:
						self.details[iface].append((impl, unusable))
					else:
						self.details[iface].append((impl, _('Not processed')))

			if best is not None:
				debug(_("Will use implementation %(implementation)s (version %(version)s)"), {'implementation': best, 'version': best.get_version()})
				self.selections[iface] = best
			elif dep.is_optional():
				info(_("Skip optional but not ready %(interface)s dependency"), {'interface': iface})
				del self.selections[iface]
			else:
				debug(_("No implementation chould be chosen yet"));

			return best is not None

		def get_implementations(iface, arch):
			debug(_("get_best_implementation(%(interface)s), with feeds: %(feeds)s"), {'interface': iface, 'feeds': iface.feeds})

			impls = []
			for f in usable_feeds(iface, arch):
				self.feeds_used.add(f)
				debug(_("Processing feed %s"), f)

				try:
					feed = self.iface_cache.get_interface(f)._main_feed
					if not feed.last_modified: continue	# DummyFeed
					if feed.name and iface.uri != feed.url and iface.uri not in feed.feed_for:
						info(_("Missing <feed-for> for '%(uri)s' in '%(feed)s'"), {'uri': iface.uri, 'feed': f})

					if feed.implementations:
						impls.extend(feed.implementations.values())
					elif return_postponed:
						postponed.extend(feed.pop_postponed())
				except Exception, ex:
					warn(_("Failed to load feed %(feed)s for %(interface)s: %(exception)s"), {'feed': f, 'interface': iface, 'exception': str(ex)})

			if not impls:
				info(_("Interface %s has no implementations!"), iface)
				return []

			return impls
		
		def compare(interface, b, a, iface_restrictions, arch):
			"""Compare a and b to see which would be chosen first.
			@param interface: The interface we are trying to resolve, which may
			not be the interface of a or b if they are from feeds.
			@rtype: int"""
			a_stab = a.get_stability()
			b_stab = b.get_stability()

			# Usable ones come first
			r = cmp(is_unusable(b, iface_restrictions, arch), is_unusable(a, iface_restrictions, arch))
			if r: return r

			machine = machine_groups.get(os.uname()[-1], 0)
			r = cmp(machine_groups.get(a.machine, 0) == machine, machine_groups.get(b.machine, 0) == machine)
			if r: return r

			# Preferred versions come first
			r = cmp(a_stab == model.preferred, b_stab == model.preferred)
			if r: return r

			if self.network_use != model.network_full:
				r = cmp(get_cached(a), get_cached(b))
				if r: return r

			# Stability
			stab_policy = interface.stability_policy
			if not stab_policy:
				if self.help_with_testing: stab_policy = model.testing
				else: stab_policy = model.stable

			if a_stab >= stab_policy: a_stab = model.preferred
			if b_stab >= stab_policy: b_stab = model.preferred

			r = cmp(a_stab, b_stab)
			if r: return r
			
			# Newer versions come before older ones
			r = cmp(a.version, b.version)
			if r: return r

			# Get best OS
			r = cmp(arch.os_ranks.get(b.os, None),
				arch.os_ranks.get(a.os, None))
			if r: return r

			# Get best machine
			r = cmp(arch.machine_ranks.get(b.machine, None),
				arch.machine_ranks.get(a.machine, None))
			if r: return r

			# Slightly prefer cached versions
			if self.network_use == model.network_full:
				r = cmp(get_cached(a), get_cached(b))
				if r: return r

			return cmp(a.id, b.id)
		
		def usable_feeds(iface, arch):
			"""Return all feeds for iface that support arch.
			@rtype: generator(ZeroInstallFeed)"""
			yield iface.uri

			for f in iface.feeds:
				# Note: when searching for src, None is not in machine_ranks
				if f.os in arch.os_ranks and \
				   (f.machine is None or f.machine in arch.machine_ranks):
					yield f.uri
				else:
					debug(_("Skipping '%(feed)s'; unsupported architecture %(os)s-%(machine)s"),
						{'feed': f, 'os': f.os, 'machine': f.machine})
		
		def is_unusable(impl, restrictions, arch):
			"""@return: whether this implementation is unusable.
			@rtype: bool"""
			return get_unusable_reason(impl, restrictions, arch) != None

		def get_unusable_reason(impl, restrictions, arch):
			"""
			@param impl: Implementation to test.
			@type restrictions: [L{model.Restriction}]
			@return: The reason why this impl is unusable, or None if it's OK.
			@rtype: str
			@note: The restrictions are for the interface being requested, not the interface
			of the implementation; they may be different when feeds are being used."""
			machine = impl.machine
			if machine and self._machine_group is not None:
				if machine_groups.get(machine, 0) != self._machine_group:
					return _("Incompatible with another selection from a different architecture group")

			for r in restrictions:
				if not r.meets_restriction(impl):
					return _("Incompatible with another selected implementation")
			stability = impl.get_stability()
			if stability <= model.buggy:
				return stability.name
			if self.network_use == model.network_offline and not get_cached(impl):
				return _("Not cached and we are off-line")
			if impl.os not in arch.os_ranks:
				return _("Unsupported OS")
			# When looking for source code, we need to known if we're
			# looking at an implementation of the root interface, even if
			# it's from a feed, hence the sneaky restrictions identity check.
			if machine not in arch.machine_ranks:
				if machine == 'src':
					return _("Source code")
				return _("Unsupported machine type")
			return None

		def get_cached(impl):
			"""Check whether an implementation is available locally.
			@type impl: model.Implementation
			@rtype: bool
			"""
			if isinstance(impl, model.DistributionImplementation):
				return impl.installed
			if impl.id.startswith('/'):
				return os.path.exists(impl.id)
			else:
				try:
					path = self.stores.lookup(impl.id)
					assert path
					return True
				except BadDigest:
					return False
				except NotStored:
					return False

		self.ready = process(model.InterfaceDependency(root_interface), arch)
		return postponed
