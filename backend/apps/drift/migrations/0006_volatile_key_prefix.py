from django.db import migrations, models


NEW_RULES = [
    # (section, spec_type, field_name, aux, description)

    # ── Per-interface sysctl namespaces ───────────────────────────────────────
    # These keys are created/destroyed with every virtual interface (virbr, docker,
    # veth, etc.) and generate constant spurious drift on busy hosts.
    ('sysctl', 'key_prefix', 'net.ipv4.conf.',          'key', 'Per-interface IPv4 sysctl parameters — created/destroyed with each interface'),
    ('sysctl', 'key_prefix', 'net.ipv6.conf.',          'key', 'Per-interface IPv6 sysctl parameters — created/destroyed with each interface'),
    ('sysctl', 'key_prefix', 'net.ipv4.neigh.',         'key', 'ARP/neighbour table per-interface parameters'),
    ('sysctl', 'key_prefix', 'net.ipv6.neigh.',         'key', 'IPv6 neighbour table per-interface parameters'),
    ('sysctl', 'key_prefix', 'kernel.sched_domain.',    'key', 'CPU scheduler topology — varies with CPU count and hotplug events'),

    # ── Additional discrete volatile sysctl keys ──────────────────────────────
    ('sysctl', 'exclude_key', 'kernel.random.read_wakeup_threshold',    'key', 'Entropy pool read-wakeup threshold (runtime)'),
    ('sysctl', 'exclude_key', 'vm.stat_interval',                       'key', 'VM statistics refresh interval (tunable, changes at runtime)'),
    ('sysctl', 'exclude_key', 'vm.drop_caches',                         'key', 'Write-only cache-drop trigger; always reads 0'),
    ('sysctl', 'exclude_key', 'net.ipv4.route.flush',                   'key', 'Write-only route-cache flush; always reads -1'),
    ('sysctl', 'exclude_key', 'net.ipv6.route.flush',                   'key', 'Write-only IPv6 route-cache flush'),
    ('sysctl', 'exclude_key', 'net.netfilter.nf_conntrack_acct',        'key', 'Conntrack accounting flag (kernel module state)'),
    ('sysctl', 'exclude_key', 'net.netfilter.nf_conntrack_buckets',     'key', 'Conntrack hash table size (adjusts with memory)'),
    ('sysctl', 'exclude_key', 'net.netfilter.nf_conntrack_events',      'key', 'Conntrack event reporting flag'),
    ('sysctl', 'exclude_key', 'net.netfilter.nf_conntrack_max',         'key', 'Maximum conntrack table entries (scales with RAM)'),
    ('sysctl', 'exclude_key', 'net.netfilter.nf_conntrack_timestamp',   'key', 'Conntrack timestamp flag'),
    ('sysctl', 'exclude_key', 'kernel.perf_cpu_time_max_percent',       'key', 'Perf subsystem CPU time cap (runtime)'),
    ('sysctl', 'exclude_key', 'kernel.perf_event_max_sample_rate',      'key', 'Perf event max sample rate (auto-tuned at runtime)'),
    ('sysctl', 'exclude_key', 'kernel.perf_event_mlock_kb',             'key', 'Perf mlock limit (runtime)'),
    ('sysctl', 'exclude_key', 'vm.zone_reclaim_mode',                   'key', 'NUMA zone reclaim mode (runtime tunable)'),
    ('sysctl', 'exclude_key', 'kernel.ngroups_max',                     'key', 'Max supplementary groups — can vary by distro patch'),

    # ── Filesystem / NFS volatile counters not yet seeded ────────────────────
    ('sysctl', 'exclude_key', 'fs.nfs.nfs_mountpoint_expiry_timeout', 'key', 'NFS mount expiry timeout counter'),
    ('sysctl', 'exclude_key', 'fs.leases-enable',                     'key', 'Lease subsystem state (runtime)'),
    ('sysctl', 'exclude_key', 'fs.lease-break-time',                  'key', 'Lease break timer (runtime)'),

    # ── Listening services: PID already seeded; also ignore local_address ────
    # (some tools bind to a random ephemeral port on loopback; the port is the
    # stable identifier tracked by the baseline, not the local IP)
    ('listening_services', 'item_field', 'local_address', '', 'Bind address may change between reboots; port is the stable identifier'),
]


def seed_rules(apps, schema_editor):
    VolatileFieldRule = apps.get_model('drift', 'VolatileFieldRule')
    for section, spec_type, field_name, aux, description in NEW_RULES:
        VolatileFieldRule.objects.get_or_create(
            section=section,
            spec_type=spec_type,
            field_name=field_name,
            aux=aux,
            defaults={'description': description},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('drift', '0005_alter_volatilefieldrule_spec_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='volatilefieldrule',
            name='spec_type',
            field=models.CharField(
                choices=[
                    ('section_field',   'Section field \u2014 drop from section dict'),
                    ('item_field',      'Item field \u2014 drop from each array item'),
                    ('nested_field',    'Nested field \u2014 drop from nested array items'),
                    ('exclude_key',     'Exclude item by key value'),
                    ('exclude_section', 'Exclude section \u2014 omit entire section from comparison'),
                    ('key_prefix',      'Exclude items whose key starts with prefix'),
                ],
                max_length=30,
            ),
        ),
        migrations.RunPython(seed_rules, migrations.RunPython.noop),
    ]
