"""Synthetic presentation load only: no inventory, catalog or engine mutation."""


class LoadMode:
    def __init__(self, metadata):
        self.available = metadata.get('test_build') is True
        self.enabled = False
        self.choice = None
        self.values = {}

    def set_enabled(self, value):
        self.enabled = bool(value) if self.available else False
        return self.enabled

    def ark_rows(self, arks):
        if not self.available:
            return []
        return (
            [
                (
                    f'Test {i + 1:03d} · {arks[i % len(arks)]["ArkName"]}\n'
                    f'Typ: {arks[i % len(arks)]["ArkType"]} · nur Belastungstest',
                    f'TEST_LOAD_ARK_{i:03d}',
                )
                for i in range(300)
            ]
            if arks
            else []
        )

    def inventory_rows(self):
        if not self.available:
            return []
        return [
            (
                f'Test-Teil {i + 1:03d}\nANG 0 · LP 0 · VER 0 · Bonus 0 · keine Spieldaten',
                f'TEST_LOAD_ITEM_{i:03d}',
            )
            for i in range(100)
        ]

    def select(self, value):
        # Never calls choose_ark/set_value; these synthetic IDs are not GameData.
        if not self.available:
            return
        if value not in {key for _, key in self.inventory_rows()} and not (
            isinstance(value, str)
            and value.startswith('TEST_LOAD_ARK_')
            and value[-3:].isdigit()
            and 0 <= int(value[-3:]) < 300
        ):
            raise ValueError('Unknown synthetic presentation row')
        self.choice = value
